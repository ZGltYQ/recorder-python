# Phase 4: Screenshot Mode - Research

**Phase:** 4
**Goal:** Users can enable interval-based screenshot capture with AI task detection and auto-solve
**Requirements:** SCRN-01, SCRN-02, SCRN-03, SCRN-04, SCRN-05, SCRN-06
**Generated:** 2026-04-14

---

## Domain Analysis

### Screenshot Capture on Linux

**Approaches:**
1. **scrot** - Simple screen capture utility, lightweight
2. **gnome-screenshot** - GNOME's built-in tool
3. **spectacle** - KDE's screenshot tool
4. **xfce4-screenshooter** - XFCE screenshot tool
5. **PyQt5/Qt screenshot** - Using QScreen from QApplication

**Recommended:** Use `mss` library (fast, cross-platform) or `pyautogui.screenshot()` which uses MSS internally. For Qt-native approach, use `QScreen.grabWindow()`.

For Linux, the most reliable approach is `mss` or using Qt's built-in `QScreen.grabWindow()` which doesn't require external dependencies.

### Screenshot Analysis with AI

**Input:** PNG image of screen
**Output:** Structured analysis of actionable tasks

**Prompt Strategy:**
```
Analyze this screenshot and identify any actionable tasks or questions 
that appear on screen. Return a JSON list of tasks found with:
- task_description: What needs to be done
- priority: high/medium/low
- context: Any relevant context from the screenshot
```

**Integration:** Use existing `AISuggestionGenerator` from `src/ai/openrouter.py` but send image as base64-encoded data.

### Circular Buffer for Screenshot Storage

**Implementation:** Use `collections.deque` with maxlen for automatic eviction.

```python
from collections import deque
screenshot_buffer = deque(maxlen=100)  # Keep last 100 screenshots
```

**Storage location:** `~/.config/recorder-python/screenshots/`
**Retention policy:** Configurable max count (default 50), auto-cleanup

### Threading Model

**Critical constraint:** Screenshots MUST NOT block audio pipeline.

**Solution:** QThread-based screenshot capture, similar to `AudioCaptureThread`:
- ScreenshotCaptureThread(QThread) - runs timer-based interval capture
- Uses QTimer for intervals (5-300 seconds, default 30s)
- Emits `screenshot_ready` signal with image data
- Never blocks main thread

### UI Integration

**Side panel modifications:**
- Add "Screenshot Tasks" section in AI Suggestions panel
- Display detected tasks with explanations
- Use existing `AISuggestionsWidget` pattern

**Settings integration:**
- Add screenshot interval setting (slider 5-300s)
- Add enable/disable toggle
- Add retention count setting

---

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|------------|
| Screenshot library | `mss` | Fast, no external deps, cross-platform |
| Capture method | QThread with QTimer | Consistent with AudioCapture pattern, Qt-native |
| Image analysis | OpenRouter API with base64 image | Reuse existing AI infrastructure |
| Storage | deque circular buffer + filesystem | Automatic eviction, persistent storage |
| Task queue | Reuse priority queue | Existing infrastructure handles ordering |

---

## Dependencies

- **Phase 3 (RAG):** AI answer generation via OpenRouter
- **Phase 2 (Local LLM):** Provider configuration
- **Phase 1 (Priority Queue):** Task ordering

---

## File Structure

```
src/
  screenshot/
    __init__.py
    capture.py      # ScreenshotCapture, ScreenshotCaptureThread
    storage.py      # ScreenshotStorage (circular buffer)
    analyzer.py     # ScreenshotAnalyzer (AI integration)
  gui/
    main_window.py  # Add screenshot toggle, interval settings
```

---

## Key Implementation Notes

1. **QScreen usage:**
```python
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

def capture_screenshot():
    screen = QApplication.primaryScreen()
    pixmap = screen.grabWindow(0)  # 0 = entire screen
    return pixmap.toImage()
```

2. **Interval timer:**
```python
self._timer = QTimer()
self._timer.timeout.connect(self._capture_and_process)
self._timer.start(interval_seconds * 1000)
```

3. **Circular buffer with persistence:**
```python
self._buffer = deque(maxlen=max_screenshots)
```

4. **AI analysis prompt:**
```
You are analyzing a screenshot for actionable tasks.
Identify any: TODOs, questions asked, action items, 
decisions made, or items requiring follow-up.
Return JSON format.
```
