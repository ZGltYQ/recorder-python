# Phase 1 Research: Priority Queue Foundation

**Phase:** 1
**Generated:** 2026-04-14
**Requirements:** PRIO-01, PRIO-02, PRIO-03, PRIO-04

---

## Research Summary

This phase implements a priority queue system for AI-generated question responses. Questions detected via keywords enter a priority (fast) queue, while background AI-detected questions enter a normal queue. The priority queue is processed first with starvation prevention via aging.

---

## Existing Code Analysis

### Question Detection (`src/ai/openrouter.py`)

**Current Implementation:**
- `QuestionDetector` class (lines 237-280) uses keyword detection
- `QUESTION_WORDS` list contains: "what", "why", "how", "when", "where", "who", "which", "can", "could", "would", "should", "is", "are", "do", "does", "did", "will", "shall", "may", "might", "am"
- Detection logic (line 267-280):
  1. Ends with "?" → is a question
  2. Starts with a QUESTION_WORD → is a question

**Key Method:**
```python
def is_question(self, text: str) -> bool:
    text_lower = text.lower().strip()
    if text.endswith("?"):
        return True
    words = text_lower.split()
    if words and words[0] in self.QUESTION_WORDS:
        return True
    return False
```

### AI Response Generation (`src/ai/openrouter.py`)

**Current Implementation:**
- `AISuggestionGenerator.generate_response()` (lines 294-324) calls OpenRouter API
- Currently called synchronously in background thread (main_window.py line 779-796)
- No queuing mechanism - all questions processed immediately in order received

**Current Flow in `main_window.py`:**
```python
if self.ai_generator.is_question(result.text):
    self.generate_ai_response(result.text, result.message_id)
```

### Database Schema (`src/database/manager.py`)

**Existing Tables:**
- `ConversationMessage` has:
  - `is_question` (Boolean) - marks if message is a question
  - `ai_response` (Text) - stores AI response

**Missing for Priority Queue:**
- Queue priority level (priority/normal)
- Queue entry timestamp (for aging calculation)
- Queue status (pending/processing/completed)

### UI Components (`src/gui/main_window.py`)

**Existing Widgets:**
- `AISuggestionsWidget` (lines 326-375) - displays AI suggestions as QListWidget
- `suggestions_widget` instance in `MainWindow` (line 582)

**Missing for PRIO-04:**
- Queue depth display showing "Priority: X | Normal: Y"

---

## Architecture Decision Points

### 1. Queue Implementation

**Option A: asyncio.PriorityQueue (per STATE.md decision)**
- Pros: Native asyncio support, built-in priority ordering, well-suited for I/O-bound tasks
- Cons: Runs in separate event loop from Qt main thread, requires careful signal integration

**Option B: queue.PriorityQueue (thread-safe, no asyncio)**
- Pros: Works with existing threading model, simpler integration with Qt
- Cons: No native asyncio support, would need adapter

**Decision: asyncio.PriorityQueue with Qt signal bridge**
- Use `asyncio.PriorityQueue` for priority ordering and aging logic
- Bridge to Qt via QObject signals for GUI updates
- Worker thread runs asyncio event loop

### 2. Question Classification

**Current:** `QuestionDetector.is_question()` for keyword detection

**For Phase 1:** 
- Keyword-detected (via `QuestionDetector.is_question()`) → PRIORITY queue
- Background AI-detected questions → NORMAL queue (future: AI could detect nuanced questions)

**Note:** Current code only does keyword detection. "AI-detected questions" in PRIO-02 refers to questions processed by AI analysis (future enhancement). For now, questions not caught by keyword detection that still trigger AI responses would go to normal queue.

### 3. Starvation Prevention (Aging)

**Approach:** Priority decay over time
- Initial priority: keyword=1, normal=2
- Every N seconds, increase effective priority of normal queue items
- Formula: `effective_priority = base_priority + (wait_time / aging_interval) * aging_factor`
- Maximum aging cap to prevent infinite promotion

**Configurable Parameters:**
- `aging_interval`: How often to apply aging (default: 30 seconds)
- `aging_factor`: How much priority increases per interval (default: 0.5)
- `max_age`: Maximum aging steps before forced processing (default: 10)

### 4. Integration with Existing Code

**Files to Modify:**
1. `src/ai/openrouter.py` - Add priority parameter to `generate_response()`
2. `src/gui/main_window.py` - Route questions to priority queue manager
3. `src/database/manager.py` - Add queue-related fields to `ConversationMessage`
4. `src/utils/config.py` - Add `PriorityQueueConfig`

**New File:**
1. `src/ai/priority_queue.py` - Priority queue manager with asyncio

---

## Key Interfaces

### PriorityQueueManager (new module)

```python
class PriorityQueueManager(QObject):
    # Signals
    response_ready = Signal(str, str)  # message_id, response
    queue_depth_changed = Signal(int, int)  # priority_count, normal_count
    error = Signal(str)
    
    # Methods
    def enqueue_question(self, question: str, message_id: str, is_priority: bool) -> None
    def start_processing(self) -> None
    def stop_processing(self) -> None
    def get_queue_depth(self) -> Tuple[int, int]  # (priority_count, normal_count)
```

### Config Additions

```python
@dataclass
class PriorityQueueConfig:
    enabled: bool = True
    aging_interval: int = 30  # seconds
    aging_factor: float = 0.5
    max_age: int = 10
    max_concurrent: int = 2
```

---

## File Structure After Phase 1

```
src/ai/
├── __init__.py
├── openrouter.py      # Modified: add priority param to generate_response
├── priority_queue.py  # New: PriorityQueueManager
```

---

## Success Criteria Verification

1. **PRIO-01: Keyword-detected questions enter priority queue**
   - When `QuestionDetector.is_question()` returns True, question goes to priority queue
   - Verification: `PriorityQueueManager` receives `is_priority=True`

2. **PRIO-02: Background AI-detected questions enter normal queue**
   - Questions not caught by keyword detection enter normal queue
   - Verification: Questions with `is_priority=False` go to normal queue

3. **PRIO-03: Priority queue answered first with aging**
   - Priority queue items processed before normal queue items
   - Aging mechanism promotes old normal queue items over time
   - Verification: Normal queue item eventually processed even if priority items keep arriving

4. **PRIO-04: Queue depth displayed in UI**
   - Status bar or widget shows "Priority: X | Normal: Y"
   - Updates when queue depths change
   - Verification: UI reflects actual queue counts

---

## Common Pitfalls

1. **Qt/Asyncio Integration:** Qt runs on main thread, asyncio runs on worker. Must use signals to communicate between them.

2. **Thread Safety:** Queue operations must be thread-safe since Qt signals can come from any thread.

3. **Aging Calculation:** Must use monotonic clock (not wall time) for consistent aging across system suspend/resume.

4. **Response Ordering:** When priority item added during normal item processing, ensure priority item is still picked up next.

---

## Testing Approach

1. **Unit Tests:** `PriorityQueueManager` with mock asyncio operations
2. **Integration Tests:** Full flow from transcription to AI response display
3. **Aging Tests:** Verify normal queue items eventually processed under continuous priority load
4. **UI Tests:** Verify queue depth display updates correctly
