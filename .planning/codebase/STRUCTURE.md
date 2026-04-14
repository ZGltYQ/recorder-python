# Codebase Structure

**Analysis Date:** 2026-04-14

## Directory Layout

```
recorder-python/
├── src/
│   ├── main.py              # Application entry point
│   ├── __init__.py          # Package marker
│   ├── gui/                 # PySide6 UI components
│   │   ├── __init__.py
│   │   ├── main_window.py   # Main application window (886 lines)
│   │   └── settings_dialog.py  # Settings UI (1085 lines)
│   ├── audio/               # Audio capture & processing
│   │   ├── __init__.py
│   │   └── capture.py       # AudioCapture, AudioSource (428 lines)
│   ├── speech/              # ASR & diarization
│   │   ├── __init__.py
│   │   ├── asr.py           # Qwen3ASR, TranscriptionManager (363 lines)
│   │   └── diarization.py  # SpeakerDiarization (333 lines)
│   ├── ai/                  # OpenRouter integration
│   │   ├── __init__.py
│   │   └── openrouter.py    # OpenRouterClient, AISuggestionGenerator (367 lines)
│   ├── database/            # SQLite models & operations
│   │   ├── __init__.py
│   │   └── manager.py       # DatabaseManager, SQLAlchemy models (316 lines)
│   └── utils/               # Utilities & config
│       ├── __init__.py
│       ├── logger.py        # structlog setup (63 lines)
│       └── config.py         # ConfigManager, dataclasses (195 lines)
├── models/                  # Downloaded ASR models (gitignored)
├── tests/                   # Unit tests (currently empty)
├── scripts/                 # Utility scripts
│   ├── download_models.py
│   ├── download_qwen_asr.py
│   └── setup.py
├── assets/                  # Application assets
├── pyproject.toml           # Project metadata, dependencies
├── requirements.txt         # Pip dependencies
├── README.md                # Project documentation
├── AppImageBuilder.yml      # Linux packaging config
└── recorder-python.desktop   # Linux desktop entry
```

## Directory Purposes

**src/gui/:**
- Purpose: All PySide6 Qt UI components
- Contains: Main window, settings dialog, custom widgets
- Key files: `main_window.py`, `settings_dialog.py`

**src/audio/:**
- Purpose: Audio capture from PulseAudio/PipeWire
- Contains: `AudioCapture` QObject, `AudioCaptureThread` QThread, `AudioSource` dataclass
- Key files: `capture.py`

**src/speech/:**
- Purpose: Speech recognition and speaker diarization
- Contains: Qwen3-ASR wrapper, TranscriptionManager, SpeakerDiarization
- Key files: `asr.py`, `diarization.py`

**src/ai/:**
- Purpose: OpenRouter API client, question detection, AI suggestions
- Contains: `OpenRouterClient`, `QuestionDetector`, `AISuggestionGenerator`
- Key files: `openrouter.py`

**src/database/:**
- Purpose: SQLite persistence via SQLAlchemy ORM
- Contains: `DatabaseManager`, `ConversationSession`, `ConversationMessage` models
- Key files: `manager.py`

**src/utils/:**
- Purpose: Shared utilities (logging, configuration)
- Contains: structlog logger setup, JSON config manager
- Key files: `logger.py`, `config.py`

**scripts/:**
- Purpose: Download and setup utility scripts
- Key files: `download_models.py`, `download_qwen_asr.py`

## Key File Locations

**Entry Points:**
- `src/main.py`: Application entry point, QApplication setup

**Configuration:**
- `src/utils/config.py`: `ConfigManager`, `AppConfig`, various config dataclasses
- `.env`: Environment variables (OpenRouter API key)

**Core Logic:**
- `src/audio/capture.py`: `AudioCapture` (audio source management, capture control)
- `src/speech/asr.py`: `Qwen3ASR`, `TranscriptionManager` (ASR processing)
- `src/speech/diarization.py`: `SpeakerDiarization` (speaker identification)
- `src/ai/openrouter.py`: `OpenRouterClient`, `AISuggestionGenerator` (AI responses)
- `src/database/manager.py`: `DatabaseManager` (SQLite operations)

**Testing:**
- `tests/`: Currently empty - no test files present

## Naming Conventions

**Files:**
- Python modules: `lowercase_with_underscores.py`
- Qt files: `lowercase_with_underscores.py`
- Example: `main_window.py`, `settings_dialog.py`, `openrouter.py`

**Directories:**
- Package directories: `lowercase_with_underscores/`
- Example: `src/gui/`, `src/audio/`, `src/speech/`

**Classes:**
- PascalCase: `MainWindow`, `AudioCapture`, `TranscriptionManager`
- Qt base classes: `QMainWindow`, `QObject`, `QThread`

**Dataclasses:**
- PascalCase: `AudioSource`, `TranscriptionResult`, `SpeakerUpdate`
- Location: Usually in same file as related class

**Functions/Methods:**
- snake_case: `start_capture()`, `process_audio()`, `get_database()`
- Private methods: `_on_audio_data()`, `_parse_source_block()`

**Constants:**
- UPPER_SNAKE_CASE: `AVAILABLE_MODELS`, `SOURCE_TYPES`

## Where to Add New Code

**New Feature/Component:**
- Primary code: Add module in appropriate `src/<module>/` directory
- Example: For a transcription display feature → `src/gui/transcription_display.py`

**New Utility:**
- Shared helpers: `src/utils/` directory
- Example: For a text processing utility → `src/utils/text.py`

**New Settings:**
- Add to `src/utils/config.py` in appropriate config dataclass
- Add UI controls in `src/gui/settings_dialog.py`
- Settings page navigation in `SettingsDialog._create_sidebar()`

**New AI Integration:**
- Add to `src/ai/` directory
- Example: `src/ai/anthropic.py` for Anthropic API

**New Database Model:**
- Add to `src/database/manager.py`
- Extend `Base` declarative class
- Add dataclass for data transfer

## Special Directories

**models/:**
- Purpose: Cached/downloaded ASR models
- Generated: Yes (by download scripts)
- Committed: No (gitignored)

**tests/:**
- Purpose: Unit and integration tests
- Generated: N/A
- Committed: Yes, but currently empty

**venv/:**
- Purpose: Python virtual environment
- Generated: Yes (by `python -m venv venv`)
- Committed: No (gitignored)

**assets/:**
- Purpose: Application icons, images
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-04-14*
