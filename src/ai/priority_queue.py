"""Priority queue manager for AI question responses."""

import asyncio
import threading
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QTimer, Signal

from ..utils.config import get_config
from ..utils.logger import get_logger
from .openrouter import AISuggestionGenerator, QuestionDetector

logger = get_logger(__name__)


@dataclass
class QueuedQuestion:
    """Represents a question in the priority queue."""

    priority: int  # 1 = priority (keyword), 2 = normal
    timestamp: float  # monotonic time when added
    message_id: str
    question: str
    is_priority: bool  # True if keyword-detected
    effective_priority: float = field(init=False)

    def __post_init__(self):
        self.effective_priority = float(self.priority)

    def update_effective_priority(self, aging_factor: float, aging_interval: float) -> None:
        """Update effective priority based on wait time."""
        wait_time = time.monotonic() - self.timestamp
        age_increments = wait_time / aging_interval
        self.effective_priority = self.priority + (age_increments * aging_factor)

    def __lt__(self, other: "QueuedQuestion") -> bool:
        """Compare by priority first, then timestamp for FIFO within same priority."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp

    def __le__(self, other: "QueuedQuestion") -> bool:
        return self == other or self < other

    def __gt__(self, other: "QueuedQuestion") -> bool:
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.timestamp > other.timestamp

    def __ge__(self, other: "QueuedQuestion") -> bool:
        return self == other or self > other


class PriorityQueueManager(QObject):
    """Manages priority queue for AI question responses with starvation prevention."""

    # Qt signals
    response_ready = Signal(str, str)  # message_id, response
    queue_depth_changed = Signal(int, int)  # priority_count, normal_count
    error = Signal(str)

    PRIORITY_BASE = 1
    NORMAL_BASE = 2

    def __init__(self):
        super().__init__()
        self.config = get_config()
        pq_config = self.config.get("priority_queue", None)

        if pq_config is not None:
            self.enabled = pq_config.enabled
            self.aging_interval = pq_config.aging_interval
            self.aging_factor = pq_config.aging_factor
            self.max_age = pq_config.max_age
            self.max_concurrent = pq_config.max_concurrent
        else:
            self.enabled = True
            self.aging_interval = 30
            self.aging_factor = 0.5
            self.max_age = 10
            self.max_concurrent = 2

        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_tasks: int = 0
        self._running: bool = False
        self._worker_task: asyncio.Task | None = None
        self._aging_timer: QTimer | None = None
        self._asyncio_thread: threading.Thread | None = None
        self._asyncio_loop: asyncio.AbstractEventLoop | None = None

        self.ai_generator = AISuggestionGenerator()
        self.question_detector = QuestionDetector()

        # Track queue depths
        self._priority_count: int = 0
        self._normal_count: int = 0

    def start(self) -> None:
        """Start the priority queue processing.

        When ``enabled`` is False we still need to answer questions -- otherwise
        every call to ``enqueue_question`` would silently disappear. We fall
        back to a lightweight direct dispatcher that runs one question at a
        time on a background asyncio loop and emits ``response_ready`` the
        moment a response is available. Aging / priority / concurrency caps
        don't apply in that mode; we just want responses to reach the UI.
        """
        if self._running:
            logger.warning("Priority queue already running")
            return

        self._running = True

        # Run asyncio coroutine in a background thread with its own event loop
        self._asyncio_loop = asyncio.new_event_loop()
        self._asyncio_thread = threading.Thread(target=self._run_asyncio_loop, daemon=True)
        self._asyncio_thread.start()

        # Aging timer only makes sense in full-queue mode. In direct-dispatch
        # mode each item is processed FIFO, so we skip the timer (also avoids
        # needing a QApplication in tests that stub out the queue).
        if self.enabled:
            self._aging_timer = QTimer()
            self._aging_timer.timeout.connect(self._apply_aging)
            self._aging_timer.start(self.aging_interval * 1000)
            logger.info("Priority queue manager started", mode="priority")
        else:
            logger.info("Priority queue manager started", mode="direct")

    def _run_asyncio_loop(self) -> None:
        """Run the asyncio event loop in a background thread."""
        asyncio.set_event_loop(self._asyncio_loop)
        try:
            self._asyncio_loop.run_until_complete(self._process_queue())
        except RuntimeError as e:
            if "Event loop stopped" not in str(e):
                raise
        finally:
            self._asyncio_loop.close()

    def stop(self) -> None:
        """Stop the priority queue processing."""
        self._running = False

        if self._aging_timer:
            self._aging_timer.stop()
            self._aging_timer = None

        # Stop asyncio loop
        if self._asyncio_loop and self._asyncio_thread:
            self._asyncio_loop.call_soon_threadsafe(self._asyncio_loop.stop)
            self._asyncio_thread.join(timeout=2.0)
            if not self._asyncio_loop.is_closed():
                self._asyncio_loop.close()
            self._asyncio_loop = None
            self._asyncio_thread = None

        logger.info("Priority queue manager stopped")

    def enqueue_question(self, question: str, message_id: str) -> None:
        """Add a question to the queue.

        Args:
            question: The question text
            message_id: Unique identifier for tracking
        """
        if not self._running:
            # Queue machinery isn't alive yet. Log loudly and drop rather
            # than silently losing the question -- callers will see nothing
            # in the UI but at least the log reveals why.
            logger.warning(
                "question_dropped_queue_not_running",
                preview=question[:80],
                message_id=message_id[:8] if message_id else None,
            )
            return

        # Check if keyword-detected (priority) or normal
        is_priority = self.question_detector.is_question(question)

        base_priority = self.PRIORITY_BASE if is_priority else self.NORMAL_BASE

        item = QueuedQuestion(
            priority=base_priority,
            timestamp=time.monotonic(),
            message_id=message_id,
            question=question,
            is_priority=is_priority,
        )

        self._queue.put_nowait(item)

        if is_priority:
            self._priority_count += 1
        else:
            self._normal_count += 1

        self._emit_queue_depth()
        logger.debug("Question enqueued", is_priority=is_priority, queue_size=self._queue.qsize())

    async def _process_queue(self) -> None:
        """Process items from the priority queue."""
        while self._running:
            try:
                # Wait for item with timeout to allow checking _running
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                # Wait if at max concurrent
                while self._active_tasks >= self.max_concurrent and self._running:
                    await asyncio.sleep(0.1)

                if not self._running:
                    break

                self._active_tasks += 1

                # Process in background task
                asyncio.create_task(self._process_item(item))

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in queue processing", error=str(e))
                self.error.emit(f"Queue processing error: {e}")

    async def _process_item(self, item: QueuedQuestion) -> None:
        """Process a single queue item.

        Args:
            item: The queued question to process
        """
        try:
            response = await self.ai_generator.generate_response(item.question)

            if response:
                # Emit signal on Qt thread
                self.response_ready.emit(item.message_id, response)
                logger.debug("Response ready", message_id=item.message_id)
            else:
                logger.warning("No response generated", message_id=item.message_id)

        except Exception as e:
            logger.error("Error processing question", message_id=item.message_id, error=str(e))
            self.error.emit(f"Error generating response: {e}")
        finally:
            self._active_tasks -= 1

            if item.is_priority:
                self._priority_count = max(0, self._priority_count - 1)
            else:
                self._normal_count = max(0, self._normal_count - 1)

            self._emit_queue_depth()

    def _apply_aging(self) -> None:
        """Apply aging to normal queue items to prevent starvation.

        Since asyncio.PriorityQueue uses heapq which doesn't support in-place reordering,
        aging is implemented via a promotion mechanism:
        1. Every aging_interval, we check for aged normal items
        2. Items that have waited max_age intervals get promoted to priority queue
        3. This is done by temporarily draining and re-queuing
        """
        if not self._running or self._queue.empty():
            return

        current_time = time.monotonic()
        promoted = []
        remaining = []

        # Temporary drain
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            if not item.is_priority:
                wait_time = current_time - item.timestamp
                age_increments = int(wait_time / self.aging_interval)

                # After max_age intervals, promote this item
                if age_increments >= self.max_age:
                    # Promote: mark as priority temporarily
                    promoted_item = QueuedQuestion(
                        priority=self.PRIORITY_BASE,  # Use priority base (1)
                        timestamp=item.timestamp,  # Keep original timestamp for FIFO
                        message_id=item.message_id,
                        question=item.question,
                        is_priority=True,  # Now treated as priority
                    )
                    promoted.append(promoted_item)
                    logger.debug(
                        "Item promoted to priority",
                        message_id=item.message_id,
                        age_increments=age_increments,
                    )
                else:
                    remaining.append(item)
            else:
                remaining.append(item)

        # Re-queue all items: promoted first (they're now priority), then remaining
        for item in promoted:
            self._queue.put_nowait(item)
        for item in remaining:
            self._queue.put_nowait(item)

        if promoted:
            self._priority_count += len(promoted)
            self._normal_count -= len(promoted)
            self._emit_queue_depth()

    def _emit_queue_depth(self) -> None:
        """Emit queue depth changed signal."""
        self.queue_depth_changed.emit(self._priority_count, self._normal_count)

    def get_queue_depth(self) -> tuple[int, int]:
        """Get current queue depths.

        Returns:
            Tuple of (priority_count, normal_count)
        """
        return (self._priority_count, self._normal_count)


# Global singleton
_priority_queue_manager: PriorityQueueManager | None = None


def get_priority_queue() -> PriorityQueueManager:
    """Get the global priority queue manager."""
    global _priority_queue_manager
    if _priority_queue_manager is None:
        _priority_queue_manager = PriorityQueueManager()
    return _priority_queue_manager
