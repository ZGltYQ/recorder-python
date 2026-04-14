# External Integrations

**Analysis Date:** 2026-04-14

## APIs & External Services

**AI/LLM Provider:**
- **OpenRouter** - Multi-provider LLM API gateway
  - Purpose: AI response generation, question detection, conversation summarization
  - SDK: httpx (async HTTP client)
  - Auth: API key via `OPENROUTER_API_KEY` env var
  - Config: `src/ai/openrouter.py`
  - Default model: `anthropic/claude-3.5-sonnet`
  - Base URL: `https://openrouter.ai/api/v1`
  - Features used:
    - `/models` - List available LLM models
    - `/chat/completions` - Generate AI responses

**Model Hub:**
- **Hugging Face** - Model repository for AI/ML models
  - Purpose: Download and cache Qwen3-ASR speech recognition models
  - SDK: transformers (AutoModelForSpeechSeq2Seq, AutoProcessor)
  - Auth: None required (public models)
  - Models:
    - `Qwen/Qwen3-ASR-0.6B` - Smaller ASR model (~1.2GB)
    - `Qwen/Qwen3-ASR-1.7B` - Larger ASR model (~3.4GB)
  - Config: `scripts/download_models.py`
  - Cache: `~/.cache/huggingface/` (default)

## Data Storage

**Database:**
- **SQLite** - Local file-based database
  - Location: `~/.config/recorder-python/data/conversations.db`
  - Client: SQLAlchemy 2.0+ with sqlite:// dialect
  - Tables:
    - `conversations` - Recording sessions
    - `messages` - Individual transcribed messages with speaker, text, timestamps
  - Implementation: `src/database/manager.py`

**File Storage:**
- **Local filesystem** - Config, cache, logs
  - Config: `~/.config/recorder-python/config.json`
  - Models: `~/.cache/huggingface/`
  - Logs: Application log files

## Authentication & Identity

**OpenRouter API:**
- Auth method: Bearer token (API key)
- Storage: `.env` file or config.json
- Env var: `OPENROUTER_API_KEY`
- Implementation: `src/ai/openrouter.py`

## Monitoring & Observability

**Logging:**
- Framework: structlog
- Output: Console + file
- Location: Configurable, defaults to `~/.config/recorder-python/logs/`
- Implementation: `src/utils/logger.py`

**No external monitoring services configured**

## CI/CD & Deployment

**Hosting:**
- **GitHub Releases** - Distribution via GitHub
  - Artifact: AppImage (Linux portable executable)
  - Release trigger: Git tags (`v*`)
  - Workflow: `.github/workflows/appimage.yml`

**CI Pipeline:**
- **GitHub Actions** - Automated builds
  - Build on: Ubuntu 22.04
  - Build types: CPU, CUDA
  - Artifacts: `.AppImage` files
  - Trigger: Tags (`v*`) and manual dispatch

**Distribution:**
- **AppImage** - Portable Linux package
  - Built with: appimage-builder
  - Recipe: `AppImageBuilder.yml`
  - Includes: Python runtime, all dependencies, application code

## Environment Configuration

**Required env vars:**
- `OPENROUTER_API_KEY` - OpenRouter API key for AI features (optional but recommended)
- `OPENROUTER_MODEL` - Model to use (default: `anthropic/claude-3.5-sonnet`)

**Optional env vars:**
- `QT_QPA_PLATFORM` - Qt platform plugin (e.g., `offscreen` for headless)
- `PYTHONPATH` - Additional Python module search paths

**Local development:**
- `.env` file in project root (not committed to git)

## Webhooks & Callbacks

**No incoming webhooks configured**

**Outgoing:**
- OpenRouter API calls (chat completions, model listing)
- Hugging Face model downloads

## Audio System Integration

**PulseAudio/PipeWire:**
- Control: pulsectl Python library + pactl CLI commands
- Purpose: List audio sources, capture audio, manage loopback modules
- Implementation: `src/audio/capture.py`
- Features:
  - List hardware sources
  - List monitor sources (application audio)
  - List application sources by process
  - Create null sinks for application capture
  - Create loopback modules for audio routing

**ALSA:**
- Library: sounddevice (portaudio)
- Purpose: Low-level audio capture and playback

## Key Dependencies at Risk

**PyTorch ecosystem:**
- `torch`, `torchaudio` - Large binary dependencies, CUDA version management
- Risk: Version mismatch between CPU/CUDA builds
- Mitigation: Separate pip indexes for CUDA builds

**Qt/PySide6:**
- Risk: Qt platform issues, OpenGL compatibility
- Mitigation: AppImage bundles Qt runtime

**Qwen3-ASR models:**
- Risk: Hugging Face availability, model deprecation
- Mitigation: Local cache, manual download script

---

*Integration audit: 2026-04-14*
