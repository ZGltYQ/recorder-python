# Architecture

**Analysis Date:** 2026-04-14

## Pattern Overview

**Overall:** PySide6 Qt Application with Signal/Slot Event-Driven Architecture

**Key Characteristics:**
- Qt-based desktop application with event-driven UI
- Asynchronous audio processing pipeline using QThread workers
- Modular plugin-style architecture for speech/diarization services
- Global singleton pattern for config and database access
- Signal/slot mechanism for loose coupling between components

## Layers

**UI Layer (GUI):**
- Purpose: User interface and visual presentation
- Location: `src/gui/`
- Contains: `main_window.py`, `settings_dialog.py`
- Depends on: All backend services
- Used by: Qt event loop

**Audio Layer:**
- Purpose: Audio capture and source management
- Location: `src/audio/capture.py`
- Contains: `AudioCapture` (QObject), `AudioCaptureThread` (QThread)
- Depends on: `utils/logger`, `utils/config`
- Used by: `gui/main_window.py`

**Speech Processing Layer:**
- Purpose: ASR transcription and speaker diarization
- Location: `src/speech/`
- Contains: `asr.py`, `diarization.py`
- Depends on: `utils/logger`, `utils/config`, audio layer
- Used by: `gui/main_window.py`

**AI Layer:**
- Purpose: OpenRouter API integration for question detection and responses
- Location: `src/ai/openrouter.py`
- Contains: `OpenRouterClient`, `QuestionDetector`, `AISuggestionGenerator`
- Depends on: `utils/logger`, `utils/config`
- Used by: `gui/main_window.py`

**Data Layer:**
- Purpose: SQLite persistence for sessions and messages
- Location: `src/database/manager.py`
- Contains: `DatabaseManager`, SQLAlchemy models
- Depends on: `utils/logger`, `utils/config`
- Used by: `gui/main_window.py`

**Utilities Layer:**
- Purpose: Shared logging, configuration management
- Location: `src/utils/`
- Contains: `logger.py`, `config.py`
- Depends on: None (base layer)
- Used by: All layers

## Data Flow

**Recording Flow:**

1. User selects audio source in `MainWindow` and clicks "Start Recording"
2. `AudioCapture.start_capture()` creates `AudioCaptureThread` to stream audio via `parec`
3. `AudioCapture` emits `audio_data` signal with raw PCM samples
4. `MainWindow.on_audio_data()` receives audio, forwards to `TranscriptionManager` and `SpeakerDiarization`
5. `ASRWorker` (QThread) buffers 3-8 seconds of audio, calls Qwen3-ASR
6. `TranscriptionResult` returned via `transcription_ready` signal
7. `MainWindow.on_transcription()` displays result, stores in database
8. `SpeakerDiarization` processes chunks, emits `speaker_updated` signals
9. AI question detection triggers async OpenRouter response generation

**Session Flow:**

1. `MainWindow.start_recording()` calls `db.create_session()`
2. Each transcription result stored via `db.add_message()`
3. Speaker updates stored via `db.update_message_speaker()`
4. AI responses stored via `db.update_ai_response()`
5. Stop recording, session persists in SQLite

## Key Abstractions

**AudioSource (dataclass):**
- Purpose: Represents an audio input source
- Examples: `src/audio/capture.py`
- Pattern: `@dataclass` with `SourceType` enum

**TranscriptionResult (dataclass):**
- Purpose: Carries transcribed text with metadata
- Examples: `src/speech/asr.py`
- Pattern: `@dataclass` returned via Qt signals

**Qwen3ASR (QObject):**
- Purpose: Wrapper around Qwen3-ASR model
- Examples: `src/speech/asr.py`
- Pattern: Qt signal-emitting object with async model loading

**DatabaseManager:**
- Purpose: SQLAlchemy ORM facade for conversations
- Examples: `src/database/manager.py`
- Pattern: Singleton via `get_database()` function

**ConfigManager:**
- Purpose: JSON-based configuration persistence
- Examples: `src/utils/config.py`
- Pattern: Singleton via `get_config()` function, dot-notation key access

## Entry Points

**Main Entry:**
- Location: `src/main.py`
- Triggers: `python -m src.main` or `recorder-python` CLI
- Responsibilities: QApplication setup, signal handlers, logging initialization, MainWindow creation

**Database Manager:**
- Location: `src/database/manager.py`
- Triggers: `get_database()` on first call
- Responsibilities: SQLite connection, session/message CRUD

**Audio Capture:**
- Location: `src/audio/capture.py`
- Triggers: User selects source and clicks record
- Responsibilities: Source enumeration, parec subprocess, Qt signal emission

## Error Handling

**Strategy:** Centralized error signal propagation

**Patterns:**
- Qt signals `error` emitted from `AudioCapture`, `TranscriptionManager`, `SpeakerDiarization`
- `MainWindow.on_error()` slot logs and displays in status bar
- Global exception handler in `main()` catches startup failures
- Logger used throughout with structured error context

## Cross-Cutting Concerns

**Logging:** structlog with JSON output to `~/.local/state/recorder-python/app.log`

**Validation:** Config values validated in setters, audio sources validated before capture start

**Authentication:** OpenRouter API key stored in config, not hardcoded

**Thread Safety:**
- QThread workers for ASR and diarization
- Qt signals/slots for thread-safe GUI updates
- Database operations use scoped sessions

---

*Architecture analysis: 2026-04-14*
