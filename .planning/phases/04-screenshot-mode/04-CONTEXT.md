# Phase 4: Screenshot Mode - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning
**Source:** Automated research and requirements analysis

<domain>
## Phase Boundary

Users can enable interval-based screenshot capture with AI task detection and auto-solve. Screenshots are analyzed for actionable tasks, which are then auto-solved by AI and displayed in the side panel.

**In scope:**
- Screenshot capture at configurable intervals (5-300 seconds, default 30s)
- QThread-based capture (never blocks audio pipeline)
- AI analysis for actionable tasks
- Auto-solve detected tasks
- Side panel display with explanations
- Circular buffer storage with retention policy

**Out of scope:**
- Real-time continuous screenshot analysis (blocks audio pipeline)
- Video recording
- Screenshot storage display in UI (SCRN-07)
- Manual screenshot trigger (SCRN-08)
</domain>

<decisions>
## Implementation Decisions

### Screenshot Capture
- Use `mss` library for cross-platform screenshot capture (or Qt's `QScreen.grabWindow()`)
- QThread with QTimer for interval-based capture
- Configurable interval: 5-300 seconds, default 30s
- Screenshot storage location: `~/.config/recorder-python/screenshots/`

### AI Analysis
- Reuse existing `AISuggestionGenerator` from `src/ai/openrouter.py`
- Send screenshot as base64-encoded image
- Prompt extracts actionable tasks as JSON

### Storage
- Circular buffer using `collections.deque(maxlen=N)`
- Configurable max count (default 50)
- Screenshots stored as PNG files on disk

### UI Integration
- Toggle in control panel to enable/disable screenshot mode
- Settings: interval slider, retention count
- "Screenshot Tasks" section in AI Suggestions side panel
- Task solutions with explanations displayed as cards

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture
- `src/audio/capture.py` — QThread pattern for non-blocking capture
- `src/ai/openrouter.py` — AISuggestionGenerator for AI analysis
- `src/gui/main_window.py` — MainWindow with side panel widget pattern

### Configuration
- `src/utils/config.py` — Config singleton pattern for settings

### Existing Patterns
- `src/speech/diarization.py` — QThread with signal/slot pattern
- `src/rag/manager.py` — ChromaDB integration pattern

</canonical_refs>

<specifics>
## Specific Ideas

**Screenshot interval setting:**
- Config key: `screenshot.interval` (int, 5-300, default 30)
- UI: Slider in control panel or settings dialog

**Retention policy:**
- Config key: `screenshot.max_count` (int, default 50)
- Circular buffer auto-evicts oldest when full

**AI analysis prompt:**
```
You are analyzing a screenshot for actionable tasks.
Identify any: TODOs, questions asked, action items, decisions made, 
or items requiring follow-up.

Return a JSON list with this format:
[
  {
    "task": "description of the task",
    "priority": "high|medium|low",
    "context": "relevant context from screenshot"
  }
]

If no tasks found, return: []
```

**Task auto-solve prompt:**
```
A screenshot analysis found this actionable task:
{task_description}

Based on the screenshot context:
{screenshot_context}

Provide a solution or recommendation for completing this task.
Be specific and actionable.
```

</specifics>

<deferred>
## Deferred Ideas

None — Phase 4 covers all v1 screenshot requirements.

**Future (SCRN-07, SCRN-08):**
- Screenshot storage display in UI (count, disk usage)
- User can manually trigger screenshot capture

</deferred>

---

*Phase: 04-screenshot-mode*
*Context gathered: 2026-04-14 via automated research*
