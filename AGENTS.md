<!-- GSD:project-start source:PROJECT.md -->
## Project

**recorder-python**

Desktop audio recording application with AI-powered transcription, speaker diarization, and real-time question detection. Records meetings/conversations, transcribes speech to text, detects when someone asks a question, and provides AI-generated answers. Supports cloud (OpenRouter) and local LLM APIs.

**Core Value:** **Capture conversations and never miss a question that can be answered.**

### Constraints

- **API Compatibility**: Local LLM must work with OpenRouter-compatible API format (chat completions endpoint)
- **Document Parsing**: Must handle multiple formats without external service dependencies
- **Privacy**: All document processing happens locally
- **Performance**: Screenshot analysis must not block main audio recording pipeline
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.10+ - All application code, desktop GUI, audio processing, AI/ML inference
- QML - UI markup (via PySide6)
- Shell - Build scripts (`build-appimage.sh`)
- YAML - Configuration (`AppImageBuilder.yml`, CI workflows)
- JSON - Configuration files
## Runtime
- Python 3.10+ (native)
- PySide6 Qt6 runtime (for GUI)
- pip (Python package manager)
- Lockfile: `requirements.txt` (pip freeze output)
## Frameworks
- PySide6 6.6.0+ - Qt6-based GUI framework for desktop application
- sounddevice 0.4.6+ - Cross-platform audio input/output
- soundfile 0.12.1+ - Audio file reading/writing (WAV, FLAC, etc.)
- pulsectl 23.5.0+ - PulseAudio/PipeWire control via D-Bus
- pyaudio 0.2.11+ - PortAudio bindings for audio capture
- transformers 4.36.0+ - Hugging Face transformers library
- torch 2.1.0+ - PyTorch deep learning framework
- torchaudio 2.1.0+ - Audio processing with PyTorch
- qwen-asr (Qwen3-ASR) - Qwen3 automatic speech recognition models
- resemblyzer 0.1.1+ - Voice encoder for speaker embeddings
- scikit-learn 1.3.0+ - Agglomerative clustering for speaker separation
- SQLAlchemy 2.0.0+ - ORM for database operations
- SQLite - Local database (`conversations.db`)
- Location: `src/database/manager.py`
- httpx 0.25.0+ - Async HTTP client for OpenRouter API
- aiohttp 3.9.0+ - Alternative async HTTP (in requirements)
- pydantic 2.5.0+ - Data validation and settings
- python-dotenv 1.0.0+ - Environment variable loading
- structlog 23.2.0+ - Structured logging
- PyYAML 6.0.1+ - YAML config parsing
- appdirs 1.4.4+ - Platform-specific directories (config, data)
- pydub 0.25.1+ - Audio manipulation
- webrtcvad 2.0.10+ - Voice activity detection
- pytest 7.4.0+ - Testing framework
- pytest-asyncio 0.21.0+ - Async test support
- black 23.0.0+ - Code formatting
- ruff 0.1.0+ - Linting
- mypy 1.7.0+ - Type checking
- hatchling - Build backend (pyproject.toml)
- appimage-builder - Linux AppImage creation
## Configuration
- `.env` file in project root for local development
- Config stored in: `~/.config/recorder-python/config.json`
- Data stored in: `~/.config/recorder-python/data/`
- `stt.language` - Language code (auto, en, ru, uk)
- `stt.model_size` - Model size (small, medium, large)
- `openrouter.api_key` - OpenRouter API key
- `openrouter.model` - Preferred LLM model
- `diarization.enabled` - Enable/disable speaker diarization
- `AppImageBuilder.yml` - AppImage build recipe
- `.github/workflows/appimage.yml` - GitHub Actions CI/CD
## Platform Requirements
- Linux (Fedora 38+, Ubuntu 22.04+)
- Python 3.10+
- 8GB RAM minimum (16GB recommended)
- Optional: NVIDIA GPU with CUDA for faster ASR
- Linux (same as development)
- AppImage distributable
- System dependencies: PipeWire/PulseAudio, ALSA, PortAudio
# Fedora/Nobara
# Ubuntu/Debian
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Languages
- Python 3.10+ - All application code
## Code Style
- Line length: 100 characters
- Target version: Python 3.10
- Line length: 100 characters
- Target version: Python 3.10
- Selects: E, F, I, N, W, UP, B, C4, SIM
- Python version: 3.10
- `warn_return_any = true`
- `disallow_untyped_defs = true`
## Naming Patterns
- Python modules: `snake_case.py`
- Example: `audio_capture.py`, `openrouter.py`
- PascalCase
- Example: `AudioCapture`, `TranscriptionManager`, `OpenRouterClient`
- snake_case
- Example: `list_sources()`, `get_available_models()`, `transcribe_audio()`
- snake_case
- Example: `source_name`, `audio_data`, `is_recording`
- SCREAMING_SNAKE_CASE for module-level constants
- Example: `BASE_URL`, `AVAILABLE_MODELS`
- Prefix with underscore: `_capture_thread`, `_is_recording`
- PascalCase name, snake_case fields
- Example: `AudioSource`, `TranscriptionResult`
## Import Organization
- Use `from ..utils.logger import get_logger` for sibling modules
- Use `from ..audio.capture import AudioCapture` for sibling packages
## Error Handling
- Use structlog with structured context
- Always include error details: `logger.error("Operation failed", error=str(e))`
- QObject signals emit error strings: `self.error.emit(str(e))`
- GUI slots receive and display errors
## Logging
## Comments
- Module-level: """Description of module."""
- Class-level: Use docstrings for public classes
- Method-level: Document public methods
## Function Design
- Return `Optional[T]` when may return None
- Return `bool` for success/failure operations
- Use signals for async GUI notifications
## Module Design
## Signal/Slot Pattern (PySide6)
## Async Patterns
## Type Annotations
- All functions must have type annotations
- Use `Optional[T]` for nullable types
- Use `Union[T1, T2]` for multiple types
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Qt-based desktop application with event-driven UI
- Asynchronous audio processing pipeline using QThread workers
- Modular plugin-style architecture for speech/diarization services
- Global singleton pattern for config and database access
- Signal/slot mechanism for loose coupling between components
## Layers
- Purpose: User interface and visual presentation
- Location: `src/gui/`
- Contains: `main_window.py`, `settings_dialog.py`
- Depends on: All backend services
- Used by: Qt event loop
- Purpose: Audio capture and source management
- Location: `src/audio/capture.py`
- Contains: `AudioCapture` (QObject), `AudioCaptureThread` (QThread)
- Depends on: `utils/logger`, `utils/config`
- Used by: `gui/main_window.py`
- Purpose: ASR transcription and speaker diarization
- Location: `src/speech/`
- Contains: `asr.py`, `diarization.py`
- Depends on: `utils/logger`, `utils/config`, audio layer
- Used by: `gui/main_window.py`
- Purpose: OpenRouter API integration for question detection and responses
- Location: `src/ai/openrouter.py`
- Contains: `OpenRouterClient`, `QuestionDetector`, `AISuggestionGenerator`
- Depends on: `utils/logger`, `utils/config`
- Used by: `gui/main_window.py`
- Purpose: SQLite persistence for sessions and messages
- Location: `src/database/manager.py`
- Contains: `DatabaseManager`, SQLAlchemy models
- Depends on: `utils/logger`, `utils/config`
- Used by: `gui/main_window.py`
- Purpose: Shared logging, configuration management
- Location: `src/utils/`
- Contains: `logger.py`, `config.py`
- Depends on: None (base layer)
- Used by: All layers
## Data Flow
## Key Abstractions
- Purpose: Represents an audio input source
- Examples: `src/audio/capture.py`
- Pattern: `@dataclass` with `SourceType` enum
- Purpose: Carries transcribed text with metadata
- Examples: `src/speech/asr.py`
- Pattern: `@dataclass` returned via Qt signals
- Purpose: Wrapper around Qwen3-ASR model
- Examples: `src/speech/asr.py`
- Pattern: Qt signal-emitting object with async model loading
- Purpose: SQLAlchemy ORM facade for conversations
- Examples: `src/database/manager.py`
- Pattern: Singleton via `get_database()` function
- Purpose: JSON-based configuration persistence
- Examples: `src/utils/config.py`
- Pattern: Singleton via `get_config()` function, dot-notation key access
## Entry Points
- Location: `src/main.py`
- Triggers: `python -m src.main` or `recorder-python` CLI
- Responsibilities: QApplication setup, signal handlers, logging initialization, MainWindow creation
- Location: `src/database/manager.py`
- Triggers: `get_database()` on first call
- Responsibilities: SQLite connection, session/message CRUD
- Location: `src/audio/capture.py`
- Triggers: User selects source and clicks record
- Responsibilities: Source enumeration, parec subprocess, Qt signal emission
## Error Handling
- Qt signals `error` emitted from `AudioCapture`, `TranscriptionManager`, `SpeakerDiarization`
- `MainWindow.on_error()` slot logs and displays in status bar
- Global exception handler in `main()` catches startup failures
- Logger used throughout with structured error context
## Cross-Cutting Concerns
- QThread workers for ASR and diarization
- Qt signals/slots for thread-safe GUI updates
- Database operations use scoped sessions
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
