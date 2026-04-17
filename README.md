# Audio Recorder STT — Python Edition

A native Python desktop application for real-time speech-to-text transcription
with speaker diarization, live question detection, and AI-generated answers.

**Core value:** capture conversations and never miss a question that can be
answered.

## Features

- 🎙️ **Real-time audio capture** — any application source via PipeWire / PulseAudio
- 🗣️ **Pluggable ASR backends** — [Qwen3-ASR](https://huggingface.co/Qwen/Qwen3-ASR-0.6B) (bundled) or [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (optional, CPU-capable)
- 🌍 **Multilingual** — English, Russian, Ukrainian; both transcription and question detection
- ❓ **Live question detection** — EN/RU/UK, WH-words + Russian `ли` clitic + Ukrainian `чи` particle; interim-dispatched so the LLM starts answering before you finish speaking
- 👥 **Speaker diarization** — Resemblyzer voice embeddings, fully offline
- 🤖 **AI answers** — OpenRouter (cloud) or local OpenAI-compatible endpoint
- 📝 **Conversation summary** — one-click LLM summary of the active session
- 📚 **Optional RAG** — drop `.txt` files, answers ground in your documents
- 💾 **Session history** — SQLite, searchable, exportable

## Performance in one table

| Phase | What changed | Effect |
|---|---|---|
| 1 | parec chunk 2.0 s → 0.1 s; warmup decode; `torch.inference_mode`; cached resampler; default model 1.7B → 0.6B; silence-trim before decode | −30-50 % end-to-end latency on default config |
| 2 | Rolling-window interim decoding (`stt.streaming.interim_strategy = window`) | Interim cost ~O(4 s) regardless of utterance length → −60 % on 12 s segments |
| 3 | webrtcvad replaces custom RMS VAD | Cleaner pause detection on noisy loopback |
| 4 | Optional faster-whisper backend | Real-time on **CPU** (was GPU-only); ~4-8× on GPU |

See `plan.md` for the full write-up.

## Prerequisites

- **OS:** Linux (Fedora 38+, Ubuntu 22.04+, or similar)
- **Python:** 3.10+
- **RAM:** 8 GB minimum (16 GB recommended)
- **GPU:** optional — Qwen3 runs best on CUDA, faster-whisper runs real-time on CPU

### System dependencies

```bash
# Fedora / Nobara
sudo dnf install pipewire pulseaudio-utils python3-pip portaudio-devel

# Ubuntu / Debian
sudo apt install pipewire pulseaudio-utils python3-pip portaudio19-dev
```

## Installation

```bash
git clone <this-repo> && cd recorder-python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The first run downloads the selected ASR model (~1.2 GB for Qwen3-ASR-0.6B,
~1.5 GB for faster-whisper `large-v3-turbo`). You can pre-fetch with:

```bash
python scripts/download_models.py
```

### OpenRouter API (for question answering and summaries)

Either set in `.env`:

```env
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

…or enter it in Settings → AI Provider. Or skip OpenRouter entirely and
point Settings → Local LLM at any OpenAI-compatible endpoint.

## Usage

```bash
python -m src.main
```

### Pick an ASR backend (Settings → ASR Model → Backend)

| Backend | Best for | Notes |
|---|---|---|
| **Qwen3-ASR** (bundled) | GPU + multilingual accuracy | Default. 0.6B = faster, 1.7B = more accurate. |
| **faster-whisper** (optional) | CPU users / extra GPU speed | `large-v3-turbo` multilingual. `compute_type=auto` picks int8_float16 on CUDA, int8 on CPU. |

Switching backend requires a restart (the dialog reminds you).

### Running tests

```bash
pytest tests/ --ignore=tests/test_rag.py -q
```

126 tests cover ASR speed-ups, backend selection and fallback, multilingual
question detection, priority-queue lifecycle, the config refactor, and the
rest of the e2e suite.

## Architecture

```
recorder-python/
├── src/
│   ├── main.py                         # Application entry point
│   ├── gui/
│   │   ├── main_window.py              # Main window, Qt signals, summary flow
│   │   └── settings_dialog.py          # Unified ASR Model + AI provider UI
│   ├── audio/
│   │   └── capture.py                  # PipeWire/PulseAudio capture (parec)
│   ├── speech/
│   │   ├── asr.py                      # Qwen3ASR + ASRWorker + TranscriptionManager
│   │   ├── faster_whisper_backend.py   # faster-whisper backend (optional)
│   │   └── diarization.py              # Resemblyzer + agglomerative clustering
│   ├── ai/
│   │   ├── openrouter.py               # OpenRouter client + QuestionDetector
│   │   ├── local_llm.py                # OpenAI-compatible local LLM client
│   │   └── priority_queue.py           # Aging priority queue for question dispatch
│   ├── rag/                            # Optional document-grounded answers
│   ├── database/                       # SQLite conversation store
│   └── utils/
│       ├── config.py                   # Nested config with back-compat aliasing
│       └── logger.py                   # structlog configuration
└── tests/
```

### ASR pipeline

```
parec (0.1s chunks)
  → AudioCaptureThread      (Qt signal)
  → TranscriptionManager.process_audio
  → ASRWorker.audio_queue   (accumulates with VAD-based silence flushing)
  → backend.transcribe_audio()   (Qwen3 or faster-whisper)
  → TranscriptionResult (is_final=False for interims, True for finals)
```

Interim results are decoded on the last `stt.streaming.interim_window_sec`
seconds only — ~3-6× cheaper on long utterances. Final results decode the
full buffer for quality.

### Question tracking

`QuestionDetector` (in `src/ai/openrouter.py`) inspects every complete sentence
inside interim *and* final transcriptions. A sentence is a question if:

- It ends with `?`, **or**
- It starts with a WH-word (`what`, `why`, `how`, `когда`, `где`, `що`, …), **or**
- Its second token is the Russian `ли` clitic, **or**
- It starts with the Ukrainian `чи` particle.

English aux-verb starts (`is`, `are`, `do`, `does`, …) only fire when the text
ends with `?`, so exclamations like "Are you kidding me!" don't trigger
spurious LLM calls.

Detected questions enter `PriorityQueueManager`, which aging-boosts older
queue items and dispatches up to `max_concurrent` concurrent calls. If the
queue is disabled in config, a direct-dispatch fallback keeps questions
flowing to the UI rather than silently dropping them.

## Configuration

Stored in `~/.config/recorder-python/config.json` as a single nested tree:

```jsonc
{
  "stt": {
    "language": "auto",                      // "auto" | "en" | "ru" | "uk"
    "backend": "qwen3",                      // "qwen3" | "faster-whisper"
    "streaming": {                           // ASRWorker knobs, shared by every backend
      "min_chunk_sec": 2.0,
      "max_chunk_sec": 12.0,
      "silence_flush_ms": 300,
      "interim_interval_sec": 1.5,
      "interim_strategy": "window",          // "window" | "full"
      "interim_window_sec": 4.0,
      "vad_backend": "webrtc",               // "webrtc" | "rms"
      "vad_aggressiveness": 2,               // 0..3
      "trim_silence_before_decode": true
    },
    "qwen3": {
      "model_size": "0.6B",                  // "0.6B" | "1.7B"
      "auto_download": true
    },
    "faster_whisper": {
      "model_size": "large-v3-turbo",        // tiny / base / small / medium / large-v3 / large-v3-turbo
      "compute_type": "auto",                // auto / int8 / int8_float16 / float16 / float32
      "device": "auto",                      // auto / cuda / cpu
      "beam_size": 5,
      "vad_filter": true,                    // faster-whisper's built-in Silero VAD
      "vad_min_silence_ms": 500
    }
  },
  "openrouter": { "api_key": "", "model": "anthropic/claude-3.5-sonnet", ... },
  "audio":      { "chunk_duration": 0.1, ... },
  "diarization": { "enabled": true, ... },
  "priority_queue": { "enabled": true, "max_concurrent": 2, ... }
}
```

### Legacy configuration — backward compatible

Older installs with top-level `qwen_asr.*` and `faster_whisper.*` keys still
load correctly. `ConfigManager.get()` and `.set()` transparently alias the
old flat keys to the new nested paths, so code (and your existing
`config.json`) keeps working without any migration step. On the next save,
the file is rewritten in the new shape.

## Key components

### Audio capture
`src/audio/capture.py` spawns `parec` as a subprocess and reads small
(`audio.chunk_duration`, default 0.1 s) PCM chunks. Hardware, monitor, and
application sources are supported. Application sources are routed through a
null-sink loopback.

### Speech recognition
Two backends, same surface. `TranscriptionManager` picks one from
`stt.backend` at startup. `ASRWorker` is backend-agnostic — it only calls
`backend.transcribe_audio(audio, sr, language)`.

### Speaker diarization
Resemblyzer voice encoder + agglomerative clustering — fully offline, no
API tokens.

### AI integration
`OpenRouterClient` and `LocalLLMClient` share the chat-completions signature.
`AISuggestionGenerator` owns a persistent event-loop thread to keep the httpx
connection pool warm across requests.

## Troubleshooting

### Audio capture isn't picking up the app

```bash
systemctl --user status pipewire pipewire-pulse
pactl list short sources
pactl list short sink-inputs       # application audio
```

### Qwen3 fails to load on CPU or old CUDA

Switch to faster-whisper in Settings → ASR Model → Backend, pick a smaller
model (`tiny` / `small`), and set compute type to `int8`. faster-whisper
runs real-time on most modern CPUs.

### "Question dropped, queue not running" in the log

`priority_queue.enabled` is `false` AND `PriorityQueueManager.start()` hasn't
been called yet. This used to drop silently; the fix at
`src/ai/priority_queue.py` warns and adds a direct-dispatch fallback so
questions still get answered.

### GPU acceleration for Qwen3

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

faster-whisper uses ctranslate2 GPU wheels automatically when available.

## License

MIT — see `LICENSE`.

## Contributing

1. Fork, branch, change, PR.
2. Keep tests passing: `pytest tests/ --ignore=tests/test_rag.py -q`.
3. New ASR streaming/VAD knobs → `ASRStreamingConfig`. New Qwen-only knobs →
   `Qwen3ModelConfig`. New faster-whisper knobs → `FasterWhisperConfig`.
   Don't add streaming knobs under the backend configs.
