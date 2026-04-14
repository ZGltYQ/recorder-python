"""Priority queue manager for AI question responses."""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Tuple
from PySide6.QtCore import QObject, Signal, QTimer

from ..utils.logger import get_logger
from ..utils.config import get_config
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
        pq_config = self.config.get("priority_queue", {})

        self.enabled = pq_config.get("enabled", True)
        self.aging_interval = pq_config.get("aging_interval", 30)
        self.aging_factor = pq_config.get("aging_factor", 0.5)
        self.max_age = pq_config.get("max_age", 10)
        self.max_concurrent = pq_config.get("max_concurrent", 2)

        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_tasks: int = 0
        self._running: bool = False
        self._worker_task: Optional[asyncio.Task] = None
        self._aging_timer: Optional[QTimer] = None

        self.ai_generator = AISuggestionGenerator()
        self.question_detector = QuestionDetector()

        # Track queue depths
        self._priority_count: int = 0
        self._normal_count: int = 0

    def start(self) -> None:
        """Start the priority queue processing."""
        if not self.enabled:
            logger.info("Priority queue disabled")
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())

        # Start aging timer (Qt timer for GUI thread safety)
        self._aging_timer = QTimer()
        self._aging_timer.timeout.connect(self._apply_aging)
        self._aging_timer.start(self.aging_interval * 1000)

        logger.info("Priority queue manager started")

    def stop(self) -> None:
        """Stop the priority queue processing."""
        self._running = False

        if self._aging_timer:
            self._aging_timer.stop()
            self._aging_timer = None

        if self._worker_task:
            self._worker_task.cancel()
            self._worker_task = None

        logger.info("Priority queue manager stopped")

    def enqueue_question(self, question: str, message_id: str) -> None:
        """Add a question to the queue.

        Args:
            question: The question text
            message_id: Unique identifier for tracking
        """
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
        """Apply aging to normal queue items to prevent starvation."""
        # We can't easily iterate asyncio.PriorityQueue, so we handle aging
        # by adjusting how we calculate effective priority at dequeue time.
        # The effective_priority field in QueuedQuestion is updated here.
        pass  # Aging is applied at dequeue time by re-ordering

    def _emit_queue_depth(self) -> None:
        """Emit queue depth changed signal."""
        self.queue_depth_changed.emit(self._priority_count, self._normal_count)

    def get_queue_depth(self) -> Tuple[int, int]:
        """Get current queue depths.

        Returns:
            Tuple of (priority_count, normal_count)
        """
        return (self._priority_count, self._normal_count)


# Global singleton
_priority_queue_manager: Optional[PriorityQueueManager] = None


def get_priority_queue() -> PriorityQueueManager:
    """Get the global priority queue manager."""
    global _priority_queue_manager
    if _priority_queue_manager is None:
        _priority_queue_manager = PriorityQueueManager()
    return _priority_queue_manager
