# recorder-python

## What This Is

Desktop audio recording application with AI-powered transcription, speaker diarization, and real-time question detection. Records meetings/conversations, transcribes speech to text, detects when someone asks a question, and provides AI-generated answers. Supports cloud (OpenRouter) and local LLM APIs.

## Core Value

**Capture conversations and never miss a question that can be answered.**

## Requirements

### Validated

- ✓ Audio capture from multiple sources (PulseAudio/PipeWire) — existing
- ✓ Speech-to-text transcription via Qwen3-ASR — existing
- ✓ Speaker diarization — existing
- ✓ Question detection during recording — existing
- ✓ AI answer generation via OpenRouter — existing
- ✓ Conversation storage in SQLite — existing
- ✓ Results displayed in side panel — existing
- ✓ SCRN-01: User can enable screenshot mode with configurable interval (seconds) — Phase 04
- ✓ SCRN-02: App captures screenshot at configured interval — Phase 04
- ✓ SCRN-03: Screenshot analyzed by AI for actionable tasks — Phase 04
- ✓ SCRN-04: Detected tasks are auto-solved by AI — Phase 04
- ✓ SCRN-05: Task solutions displayed in side panel with explanation — Phase 04

### Active

- [ ] **LLM-01**: User can configure custom LLM API endpoint (URL + model name)
- [ ] **LLM-02**: User can select which LLM provider to use per conversation (OpenRouter or Local)
- [ ] **LLM-03**: App calls local LLM API with same interface as OpenRouter
- [ ] **RAG-01**: User can upload documents (PDF, TXT, MD, DOCX, ODT, RTF, EPUB)
- [ ] **RAG-02**: Uploaded documents are parsed and stored
- [ ] **RAG-03**: When question is detected, app searches document knowledge base
- [ ] **RAG-04**: Relevant document context included in AI prompt for answering
- [ ] **RAG-05**: Answers sourced from documents are clearly indicated
- [ ] **PRIO-01**: Keyword-detected questions enter priority answer queue
- [ ] **PRIO-02**: Background AI-detected questions enter normal queue
- [ ] **PRIO-03**: Priority queue answered before normal queue

### Out of Scope

- App hosting/running local LLM models — user provides API endpoint only
- TTS/speech output — answers displayed only in side panel
- Video recording — screenshots are image captures only
- Document editing — upload and search only

## Context

**Existing Architecture:**
- PySide6 Qt6 desktop app with signal/slot event-driven architecture
- Audio capture via PulseAudio/PipeWire (parec subprocess)
- Qwen3-ASR for transcription (local model)
- OpenRouter API for question detection and answer generation
- SQLite database for conversation/session storage
- Existing question detection uses AI analysis

**Technology Stack:**
- Python 3.10+, PySide6 6.6.0+, SQLAlchemy 2.0.0+
- Audio: sounddevice, soundfile, pulsectl, pyaudio
- AI: transformers, torch, httpx (async HTTP)
- Storage: SQLite, file system for documents

## Constraints

- **API Compatibility**: Local LLM must work with OpenRouter-compatible API format (chat completions endpoint)
- **Document Parsing**: Must handle multiple formats without external service dependencies
- **Privacy**: All document processing happens locally
- **Performance**: Screenshot analysis must not block main audio recording pipeline

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Local LLM via API only | App not designed to run inference, user's infrastructure handles it | — Pending |
| RAG on local documents only | Privacy, no external service dependency | — Pending |
| Screenshot auto-solve | User enabled feature, reduces manual intervention | — Pending |
| Keyword priority queue | Fast detection needed for real-time feel | — Pending |
| Interval-based screenshots | Simple, predictable, user-configurable | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-14 after initialization*
