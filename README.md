# Audio Recorder STT - Python Edition

A native Python desktop application for real-time speech-to-text transcription with speaker diarization and AI assistance.

## Features

- 🎙️ **Real-time Audio Capture** - Capture audio from any application using PipeWire/PulseAudio
- 🗣️ **Speech-to-Text** - Real-time transcription using Qwen3 ASR
- 👥 **Speaker Diarization** - Automatically identify and separate different speakers
- 🤖 **AI Assistance** - Automatic question detection and response generation via OpenRouter API
- 📝 **Conversation Summary** - Summarize conversations with LLM
- 💾 **History Management** - Store and search conversation history
- 🐧 **Linux Native** - Built specifically for Linux

## Prerequisites

- **OS**: Linux (Fedora 38+, Ubuntu 22.04+, or similar)
- **Python**: 3.10 or higher
- **RAM**: 8GB minimum (16GB recommended)
- **GPU**: Optional (for better ASR performance)

### System Dependencies

```bash
# Fedora/Nobara
sudo dnf install pipewire pulseaudio-utils python3-pip portaudio-devel

# Ubuntu/Debian
sudo apt install pipewire pulseaudio-utils python3-pip portaudio19-dev
```

## Installation

### 1. Clone the repository

```bash
cd /home/zgltyq/pythonRecorder/recorder-python
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Download Qwen3 ASR model

The app will automatically download the model on first run, or you can pre-download:

```bash
python scripts/download_models.py
```

### 5. Configure OpenRouter API (Optional)

Create a `.env` file:

```env
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

## Usage

### Run the application

```bash
python -m src.main
```

### Development mode

```bash
# Run with hot reload (using watchdog)
python -m src.main --dev

# Run tests
pytest tests/
```

## Architecture

```
recorder-python/
├── src/
│   ├── main.py              # Application entry point
│   ├── gui/                 # PySide6 UI components
│   ├── audio/               # Audio capture & processing
│   ├── speech/              # ASR & diarization
│   ├── ai/                  # OpenRouter integration
│   ├── database/            # SQLite models & operations
│   └── utils/               # Utilities & config
├── models/                  # Downloaded ASR models
└── tests/                   # Unit & integration tests
```

## Key Components

### Audio Capture
- Uses `pulsectl` for PulseAudio/PipeWire control
- Supports hardware, monitor, and application sources
- Real-time streaming to ASR pipeline

### Speech Recognition (Qwen3 ASR)
- Based on Qwen2-Audio or Qwen-Audio model
- Real-time transcription with low latency
- Multilingual support

### Speaker Diarization
- Uses Resemblyzer for voice embeddings
- Agglomerative clustering for speaker separation
- No API tokens required - completely offline

### AI Integration
- OpenRouter API for question detection
- Context-aware response generation
- Support for multiple LLM providers

## Migration from Electron Version

This Python version replaces the previous Electron/JavaScript implementation with several advantages:

1. **Simpler Architecture** - No Node.js/Electron overhead
2. **Better Performance** - Native Python libraries
3. **Easier Maintenance** - Single language codebase
4. **Modern ASR** - Qwen3 instead of Vosk
5. **Improved Speaker ID** - Better accuracy with same Resemblyzer backend

### Data Migration

Settings and conversation history from the Electron version can be migrated:

```bash
python scripts/migrate_from_electron.py --source /path/to/electron/app
```

## Configuration

Configuration is stored in:
- Linux: `~/.config/recorder-python/`

Key settings:
- `stt.language`: Language code (auto, en, ru, uk, etc.)
- `stt.model_size`: Model size (small, medium, large)
- `openrouter.api_key`: OpenRouter API key
- `openrouter.model`: Preferred LLM model

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Troubleshooting

### Audio Capture Issues

Check PipeWire/PulseAudio status:
```bash
systemctl --user status pipewire pipewire-pulse
pactl list short sources
```

### Model Loading Issues

Ensure sufficient RAM and disk space:
```bash
# Check available memory
free -h

# Check disk space
df -h ~/.cache/
```

### GPU Acceleration

To use GPU for ASR:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```
