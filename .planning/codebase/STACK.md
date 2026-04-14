# Technology Stack

**Analysis Date:** 2026-04-14

## Languages

**Primary:**
- Python 3.10+ - All application code, desktop GUI, audio processing, AI/ML inference
- QML - UI markup (via PySide6)
- Shell - Build scripts (`build-appimage.sh`)

**Secondary:**
- YAML - Configuration (`AppImageBuilder.yml`, CI workflows)
- JSON - Configuration files

## Runtime

**Environment:**
- Python 3.10+ (native)
- PySide6 Qt6 runtime (for GUI)

**Package Manager:**
- pip (Python package manager)
- Lockfile: `requirements.txt` (pip freeze output)

## Frameworks

**Core:**
- PySide6 6.6.0+ - Qt6-based GUI framework for desktop application
  - Location: `src/gui/`
  - Usage: Main window, settings dialog, all UI components

**Audio Processing:**
- sounddevice 0.4.6+ - Cross-platform audio input/output
- soundfile 0.12.1+ - Audio file reading/writing (WAV, FLAC, etc.)
- pulsectl 23.5.0+ - PulseAudio/PipeWire control via D-Bus
- pyaudio 0.2.11+ - PortAudio bindings for audio capture

**Speech Recognition (ASR):**
- transformers 4.36.0+ - Hugging Face transformers library
- torch 2.1.0+ - PyTorch deep learning framework
- torchaudio 2.1.0+ - Audio processing with PyTorch
- qwen-asr (Qwen3-ASR) - Qwen3 automatic speech recognition models
  - Models downloaded from Hugging Face: `Qwen/Qwen3-ASR-0.6B`, `Qwen/Qwen3-ASR-1.7B`

**Speaker Diarization:**
- resemblyzer 0.1.1+ - Voice encoder for speaker embeddings
- scikit-learn 1.3.0+ - Agglomerative clustering for speaker separation

**Database:**
- SQLAlchemy 2.0.0+ - ORM for database operations
- SQLite - Local database (`conversations.db`)
- Location: `src/database/manager.py`

**AI Integration:**
- httpx 0.25.0+ - Async HTTP client for OpenRouter API
- aiohttp 3.9.0+ - Alternative async HTTP (in requirements)

**Validation & Config:**
- pydantic 2.5.0+ - Data validation and settings
- python-dotenv 1.0.0+ - Environment variable loading

**Logging:**
- structlog 23.2.0+ - Structured logging
- PyYAML 6.0.1+ - YAML config parsing

**Utilities:**
- appdirs 1.4.4+ - Platform-specific directories (config, data)
- pydub 0.25.1+ - Audio manipulation
- webrtcvad 2.0.10+ - Voice activity detection

**Development/Testing:**
- pytest 7.4.0+ - Testing framework
- pytest-asyncio 0.21.0+ - Async test support
- black 23.0.0+ - Code formatting
- ruff 0.1.0+ - Linting
- mypy 1.7.0+ - Type checking

**Build:**
- hatchling - Build backend (pyproject.toml)
- appimage-builder - Linux AppImage creation

## Configuration

**Environment:**
- `.env` file in project root for local development
- Config stored in: `~/.config/recorder-python/config.json`
- Data stored in: `~/.config/recorder-python/data/`

**Key config options:**
- `stt.language` - Language code (auto, en, ru, uk)
- `stt.model_size` - Model size (small, medium, large)
- `openrouter.api_key` - OpenRouter API key
- `openrouter.model` - Preferred LLM model
- `diarization.enabled` - Enable/disable speaker diarization

**Build Config:**
- `AppImageBuilder.yml` - AppImage build recipe
- `.github/workflows/appimage.yml` - GitHub Actions CI/CD

## Platform Requirements

**Development:**
- Linux (Fedora 38+, Ubuntu 22.04+)
- Python 3.10+
- 8GB RAM minimum (16GB recommended)
- Optional: NVIDIA GPU with CUDA for faster ASR

**Production:**
- Linux (same as development)
- AppImage distributable
- System dependencies: PipeWire/PulseAudio, ALSA, PortAudio

**System Dependencies:**
```bash
# Fedora/Nobara
sudo dnf install pipewire pulseaudio-utils python3-pip portaudio-devel

# Ubuntu/Debian
sudo apt install pipewire pulseaudio-utils python3-pip portaudio19-dev
```

---

*Stack analysis: 2026-04-14*
