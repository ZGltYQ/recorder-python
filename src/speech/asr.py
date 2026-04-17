"""Qwen3-ASR (Automatic Speech Recognition) module."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from ..utils.config import get_config
from ..utils.logger import get_logger

# Optional imports with fallbacks
try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

try:
    import torchaudio

    TORCHAUDIO_AVAILABLE = True
except ImportError:
    TORCHAUDIO_AVAILABLE = False
    torchaudio = None

try:
    from qwen_asr import Qwen3ASRModel

    QWEN_ASR_AVAILABLE = True
except ImportError:
    QWEN_ASR_AVAILABLE = False
    Qwen3ASRModel = None

logger = get_logger(__name__)


@dataclass
class TranscriptionResult:
    """Represents a transcription result."""

    text: str
    timestamp: float
    is_final: bool
    speaker: str | None = None
    message_id: str | None = None
    confidence: float | None = None


class Qwen3ASR(QObject):
    """Qwen3 Automatic Speech Recognition."""

    # Signals
    transcription_ready = Signal(TranscriptionResult)
    model_loaded = Signal(bool)
    error = Signal(str)

    # Available model sizes. Both are published by Qwen on Hugging Face
    # (https://huggingface.co/Qwen/Qwen3-ASR-0.6B and .../Qwen3-ASR-1.7B).
    # This dict is authoritative: any model size not listed here falls back
    # to DEFAULT_MODEL_SIZE with a warning rather than trying a bogus repo.
    AVAILABLE_MODELS = {
        "0.6B": {
            "name": "Qwen/Qwen3-ASR-0.6B",
            "description": "Smaller, faster model (~0.6B params)",
            "vram_gb": 2.0,
        },
        "1.7B": {
            "name": "Qwen/Qwen3-ASR-1.7B",
            "description": "Larger, more accurate model (~1.7B params)",
            "vram_gb": 4.0,
        },
    }
    # Default to the 0.6B model: ~2-3× faster than 1.7B, still supports
    # EN/RU/UK, fits in ~2 GB VRAM. Users can opt in to 1.7B via settings.
    DEFAULT_MODEL_SIZE = "0.6B"

    def __init__(self, model_size: str = DEFAULT_MODEL_SIZE):
        super().__init__()
        self.model = None
        self.device = None
        self.is_loaded = False
        if model_size not in self.AVAILABLE_MODELS:
            logger.warning(
                "Unknown model size in config, falling back",
                requested=model_size,
                fallback=self.DEFAULT_MODEL_SIZE,
            )
            model_size = self.DEFAULT_MODEL_SIZE
        self.model_size = model_size
        self.model_name = self.AVAILABLE_MODELS[self.model_size]["name"]
        self.model_info = self.AVAILABLE_MODELS[self.model_size]
        # Cache of torchaudio Resample modules keyed by (orig_sr, target_sr)
        # so we don't rebuild a filterbank on every call. In practice there's
        # usually only one entry because parec already captures at 16 kHz.
        self._resampler_cache: dict = {}

    def load_model(self, model_size: str | None = None, device: str = "auto") -> bool:
        """Load the Qwen3-ASR model."""
        if not QWEN_ASR_AVAILABLE or not TORCH_AVAILABLE:
            logger.error("Required libraries not available")
            self.error.emit("Required libraries (qwen-asr, torch) not installed")
            return False

        # Update model size if provided
        if model_size and model_size in self.AVAILABLE_MODELS:
            self.model_size = model_size
            self.model_name = self.AVAILABLE_MODELS[model_size]["name"]
            self.model_info = self.AVAILABLE_MODELS[model_size]

        try:
            logger.info("Loading Qwen3-ASR model", model=self.model_name, size=self.model_size)

            # Determine device
            if device == "auto":
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                self.device = device

            logger.info("Using device", device=self.device)

            # Load model using qwen-asr package
            torch_dtype = torch.bfloat16 if self.device == "cuda" else torch.float32

            # max_new_tokens is set at model-build time by qwen-asr (not per
            # transcribe call), so we keep the original generous 256 here.
            # Short utterances still return early -- the generator stops on
            # the EOS token rather than padding to the cap.
            from_pretrained_kwargs = {
                "dtype": torch_dtype,
                "device_map": self.device if self.device == "cuda" else "cpu",
                "max_inference_batch_size": 1,
                "max_new_tokens": 256,
            }

            # Try local cache first to avoid a network round-trip when the
            # model is already downloaded. transformers raises OSError (not
            # FileNotFoundError) on cache miss with local_files_only=True --
            # the old `except FileNotFoundError` therefore never triggered
            # and users saw a misleading "couldn't connect to huggingface.co"
            # even when they had internet. Catch broadly and fall through to
            # a networked fetch iff auto-download is enabled.
            try:
                self.model = Qwen3ASRModel.from_pretrained(
                    self.model_name,
                    local_files_only=True,
                    **from_pretrained_kwargs,
                )
            except Exception as cache_miss:  # noqa: BLE001
                auto_download = get_config().get("qwen_asr.auto_download", True)
                if not auto_download:
                    # Re-raise with a clearer message than the transformers default.
                    raise RuntimeError(
                        f"{self.model_name} is not cached locally and auto-download "
                        f"is disabled. Open Settings → Download Models, or enable "
                        f"'Auto-download model if not present'. (underlying: {cache_miss})"
                    ) from cache_miss
                logger.info(
                    "Model not cached locally, downloading...",
                    model=self.model_name,
                    cache_miss=str(cache_miss).splitlines()[0],
                )
                self.model = Qwen3ASRModel.from_pretrained(
                    self.model_name,
                    **from_pretrained_kwargs,
                )

            self.is_loaded = True

            # Warm the model with 1 s of silence so the first real utterance
            # doesn't pay kernel-autotune / allocator cold-start (500-2000 ms).
            # Wrapped in try/except because a warmup failure should NEVER
            # block the app from starting -- worst case the first utterance
            # is just a bit slower.
            try:
                t0 = __import__("time").time()
                warm_audio = np.zeros(16000, dtype=np.float32)
                with torch.inference_mode():
                    self.model.transcribe(audio=(warm_audio, 16000))
                logger.info("asr_warmup_done", warmup_sec=round(__import__("time").time() - t0, 3))
            except Exception as warm_err:  # noqa: BLE001
                logger.warning("asr_warmup_failed", error=str(warm_err))

            self.model_loaded.emit(True)
            logger.info("Qwen3-ASR model loaded successfully")
            return True

        except Exception as e:
            logger.error("Failed to load Qwen3-ASR model", error=str(e))
            self.error.emit(f"Failed to load model: {str(e)}")
            self.model_loaded.emit(False)
            return False

    def transcribe_audio(
        self,
        audio_data: np.ndarray | str | Path,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult | None:
        """Transcribe audio data to text."""
        if not self.is_loaded:
            logger.error("Model not loaded")
            return None

        try:
            import time

            # Convert numpy array to format expected by the model
            if isinstance(audio_data, np.ndarray):
                # Ensure correct shape and dtype
                if audio_data.dtype != np.float32:
                    # Convert from int16 to float32
                    audio_data = audio_data.astype(np.float32) / 32768.0

                # Ensure mono
                if len(audio_data.shape) > 1:
                    audio_data = audio_data.mean(axis=1)

                # Resample if necessary
                if sample_rate != 16000:
                    audio_data = self._resample_audio(audio_data, sample_rate, 16000)

                # qwen-asr accepts (np.ndarray, sr) tuple
                audio_input = (audio_data, 16000)
            else:
                # File path
                audio_input = str(audio_data)

            # Resolve language: explicit arg > config > auto-detect
            cfg_lang = get_config().get("stt.language", "auto") if language is None else language
            lang_map = {
                "auto": None,
                "en": "English",
                "ru": "Russian",
                "uk": "Ukrainian",
            }
            lang_arg = lang_map.get(cfg_lang, cfg_lang) if cfg_lang else None

            transcribe_kwargs = {"audio": audio_input}
            if lang_arg:
                transcribe_kwargs["language"] = lang_arg

            # torch.inference_mode() disables autograd and version tracking --
            # ~5 % faster and less peak memory than plain no_grad for generate().
            if TORCH_AVAILABLE and torch is not None:
                with torch.inference_mode():
                    results = self.model.transcribe(**transcribe_kwargs)
            else:
                results = self.model.transcribe(**transcribe_kwargs)

            # Extract text from result
            if results and len(results) > 0:
                result = results[0]
                text = result.text.strip()

                if text:
                    # A stable message_id is required downstream: main_window
                    # gates DB save, question detection, LLM dispatch and RAG
                    # on `result.message_id`. Without it, transcripts show up
                    # in the UI but nothing else fires.
                    import uuid

                    return TranscriptionResult(
                        text=text,
                        timestamp=time.time() * 1000,
                        is_final=True,
                        message_id=str(uuid.uuid4()),
                        confidence=None,
                    )

            return None

        except Exception as e:
            logger.error("Transcription error", error=str(e))
            self.error.emit(f"Transcription error: {str(e)}")
            return None

    def _resample_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio to target sample rate.

        Caches the torchaudio ``Resample`` module per (orig_sr, target_sr)
        pair: building the Kaiser / sinc filterbank is cheap but non-free,
        and we call this once per transcribe.
        """
        if orig_sr == target_sr:
            return audio

        if (
            TORCHAUDIO_AVAILABLE
            and torchaudio is not None
            and TORCH_AVAILABLE
            and torch is not None
        ):
            key = (int(orig_sr), int(target_sr))
            resampler = self._resampler_cache.get(key)
            if resampler is None:
                resampler = torchaudio.transforms.Resample(orig_sr, target_sr)
                self._resampler_cache[key] = resampler
            audio_tensor = torch.from_numpy(audio).unsqueeze(0)
            resampled = resampler(audio_tensor)
            return resampled.squeeze(0).numpy()
        else:
            # Fallback: simple linear interpolation
            from scipy import signal

            num_samples = int(len(audio) * target_sr / orig_sr)
            return signal.resample(audio, num_samples)

    def is_ready(self) -> bool:
        """Check if the model is loaded and ready."""
        return self.is_loaded

    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "name": self.model_name,
            "size": self.model_size,
            "loaded": self.is_loaded,
            "device": self.device,
            "description": self.model_info.get("description", ""),
            "vram_required_gb": self.model_info.get("vram_gb", 0),
        }

    @classmethod
    def list_available_models(cls) -> dict:
        """List all available Qwen3-ASR model sizes."""
        return cls.AVAILABLE_MODELS.copy()


class TranscriptionManager(QObject):
    """Manager for transcription operations.

    Owns the active ASR backend (Qwen3 or faster-whisper). The backend is
    picked once on construction from ``stt.backend`` in config; switching
    backends at runtime requires a restart (a full unload/reload is possible
    via ``reload_model`` but is intentionally kept simple).
    """

    transcription_ready = Signal(TranscriptionResult)
    speaker_updated = Signal(str, str)  # message_id, speaker
    error = Signal(str)

    def __init__(self):
        super().__init__()
        config = get_config()
        self.backend_name = str(config.get("stt.backend", "qwen3")).lower()
        self.asr = self._build_backend(self.backend_name)
        self.worker = None
        self.audio_buffer = []

    @staticmethod
    def _build_backend(name: str):
        """Instantiate the requested backend. Falls back to Qwen3 if the
        requested backend isn't importable (e.g. faster-whisper not installed)
        so the app can still start."""
        config = get_config()
        if name == "faster-whisper":
            fw_cls = None
            fw_available = False
            try:
                from .faster_whisper_backend import (
                    FASTER_WHISPER_AVAILABLE as _fw_avail,
                )
                from .faster_whisper_backend import (
                    FasterWhisperASR as _fw_cls,
                )

                fw_cls = _fw_cls
                fw_available = _fw_avail
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to import faster-whisper backend", error=str(e))
            if fw_available and fw_cls is not None:
                model_size = config.get("faster_whisper.model_size", "large-v3-turbo")
                logger.info("asr_backend_selected", backend="faster-whisper", model=model_size)
                return fw_cls(model_size=model_size)
            logger.warning(
                "faster-whisper backend requested but not available, falling back to qwen3"
            )
            # Fall through to qwen3.

        # Default: Qwen3-ASR.
        model_size = config.get("qwen_asr.model_size", Qwen3ASR.DEFAULT_MODEL_SIZE)
        logger.info("asr_backend_selected", backend="qwen3", model=model_size)
        return Qwen3ASR(model_size=model_size)

    def initialize(self) -> bool:
        """Initialize the ASR model."""
        self.asr.model_loaded.connect(self._on_model_loaded)
        self.asr.error.connect(self.error.emit)
        # The backend holds its own configured size; passing None lets it
        # re-read from config if it wants to (qwen3 does this).
        return self.asr.load_model()

    def _on_model_loaded(self, success: bool):
        """Handle model loaded signal."""
        if success:
            logger.info("ASR model loaded successfully")
        else:
            logger.error("Failed to load ASR model")

    def start(self):
        """Start transcription processing."""
        if self.asr.is_ready():
            self.worker = ASRWorker(self.asr)
            self.worker.transcription_ready.connect(self.transcription_ready.emit)
            self.worker.error_occurred.connect(self.error.emit)
            self.worker.start()
            logger.info("Transcription manager started")
        else:
            logger.error("Cannot start transcription - ASR not ready")
            self.error.emit("ASR not initialized")

    def stop(self):
        """Stop transcription processing."""
        if self.worker:
            self.worker.stop()
            self.worker = None
        logger.info("Transcription manager stopped")

    def process_audio(self, audio_data: np.ndarray, sample_rate: int = 16000):
        """Process audio data for transcription."""
        if self.worker:
            self.worker.add_audio(audio_data, sample_rate)

    def reload_model(self, model_size: str) -> bool:
        """Hot-swap the ASR model to a different size.

        Stops any running worker, releases the current model (and GPU memory
        if applicable), loads the requested size, and -- if a worker was
        active before -- restarts it. Blocking; typically 10-30 s depending
        on model size and cache state.

        Returns True on success, False if the new model failed to load (in
        which case the manager is left in an unloaded state and the UI
        should surface the error via the ``error`` signal).
        """
        if model_size not in Qwen3ASR.AVAILABLE_MODELS:
            logger.error("reload_model: unknown size", requested=model_size)
            return False
        if self.asr.is_loaded and self.asr.model_size == model_size:
            logger.info("reload_model: already on requested size, skipping", size=model_size)
            return True

        was_running = self.worker is not None
        if was_running:
            self.stop()

        # Release the old model. Explicit del + gc + empty_cache() is what
        # transformers docs recommend for freeing GPU tensors.
        logger.info("reload_model: unloading current model", previous=self.asr.model_size)
        import gc

        self.asr.model = None
        self.asr.is_loaded = False
        gc.collect()
        try:
            if TORCH_AVAILABLE and torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:  # noqa: BLE001
            logger.warning("torch.cuda.empty_cache failed (non-fatal)", error=str(e))

        ok = self.asr.load_model(model_size=model_size)
        if ok and was_running:
            self.start()
        return ok


class ASRWorker(QThread):
    """Background worker for ASR processing.

    Flushes the audio buffer on natural pauses (VAD-detected silence) rather
    than on a fixed time window, so sentences don't get split mid-phrase.
    Falls back to a hard time backstop to keep memory bounded.
    """

    transcription_ready = Signal(TranscriptionResult)
    error_occurred = Signal(str)

    def __init__(self, asr_model: Qwen3ASR):
        super().__init__()
        self.asr_model = asr_model
        self.audio_queue = []
        self.audio_buffer = []
        self.buffer_duration = 0.0

        cfg = get_config()
        # Earliest a flush (finalization) is allowed (seconds of accumulated audio).
        self.min_process_duration = float(cfg.get("qwen_asr.min_chunk_sec", 2.0))
        # Hard backstop: finalize even without a pause past this many seconds.
        self.max_process_duration = float(cfg.get("qwen_asr.max_chunk_sec", 12.0))
        # Trailing silence (ms) that counts as a natural pause.
        self.silence_flush_ms = int(cfg.get("qwen_asr.silence_flush_ms", 300))
        # Interim ("streaming") emits: while accumulating a segment we re-run
        # the ASR on the growing buffer every ``interim_interval_sec`` and
        # emit the result with ``is_final=False`` so the UI can show
        # live-updating text. 0 disables interim emits.
        self.interim_interval_sec = float(cfg.get("qwen_asr.interim_interval_sec", 1.5))
        # Don't start emitting interims until the buffer has at least this
        # many seconds of audio -- Qwen3-ASR's output on <1s tends to be
        # unreliable / hallucinatory.
        self.interim_min_buffer_sec = float(cfg.get("qwen_asr.interim_min_buffer_sec", 1.2))
        # Seconds of tail audio carried into next chunk when we backstop-flush,
        # so a word straddling the cut isn't lost.
        self.backstop_tail_sec = float(cfg.get("qwen_asr.backstop_tail_sec", 0.5))
        # RMS threshold (float, audio in [-1, 1]) below which a frame is
        # counted as silence. ~0.005 ≈ -46 dBFS (quiet-room floor). Used as
        # a floor; the actual threshold per probe is dynamically raised based
        # on the observed noise floor so loopback/room audio doesn't get
        # stuck at the 15 s backstop. Raise if still missing pauses.
        self.silence_rms_threshold = float(cfg.get("qwen_asr.silence_rms_threshold", 0.005))
        # Adaptive component: a frame counts as silence when its RMS falls
        # below ``max(silence_rms_threshold, median_rms * silence_relative_ratio)``.
        # 0.35 is more aggressive than the earlier default 0.5 -- requires
        # only a ~9 dB drop to detect a pause, which matches real speech
        # against continuous background audio (app loopback, music beds).
        self.silence_relative_ratio = float(cfg.get("qwen_asr.silence_relative_ratio", 0.35))
        # VAD backend used for silence detection. "webrtc" uses webrtcvad
        # when available and falls back to "rms" if the import fails; "rms"
        # forces the legacy RMS path.
        self.vad_backend = str(cfg.get("qwen_asr.vad_backend", "webrtc")).lower()
        # webrtcvad aggressiveness (0-3). 2 is a good compromise; 3 cuts
        # more aggressively and is useful in noisy loopback.
        self.vad_aggressiveness = int(cfg.get("qwen_asr.vad_aggressiveness", 2))
        # Interim decoding strategy. "full" = re-decode the whole buffer on
        # every interim (old behaviour). "window" = only decode the last
        # ``interim_window_sec`` seconds -- cuts interim CPU/GPU ~3-6x on
        # long utterances while keeping the final pass identical.
        self.interim_strategy = str(cfg.get("qwen_asr.interim_strategy", "window")).lower()
        self.interim_window_sec = float(cfg.get("qwen_asr.interim_window_sec", 4.0))
        # Trim leading/trailing silence from the buffer before transcribing.
        # Typical 12 s backstop flush has 0.3-0.8 s of silence that still
        # gets encoded; removing it is free on CPU but saves GPU cycles.
        self.trim_silence_before_decode = bool(cfg.get("qwen_asr.trim_silence_before_decode", True))

        # Resolved webrtcvad instance, or None if fallback to RMS is in use.
        self._webrtc_vad = self._init_webrtc_vad()

        self.sample_rate = 16000
        self.is_running = False

        # Segment tracking: a "segment" is a span of audio between two
        # finalizations. Interim emits during a segment share a
        # ``_current_segment_id`` so the UI can update a single message in
        # place; the final emit uses the same id and flips ``is_final=True``.
        self._current_segment_id: str | None = None
        self._last_interim_time: float = 0.0

    def _init_webrtc_vad(self):
        """Try to set up webrtcvad. Returns a Vad instance or None."""
        if self.vad_backend != "webrtc":
            return None
        try:
            import webrtcvad  # type: ignore[import-not-found]
        except ImportError:
            logger.warning("webrtcvad not installed, falling back to RMS VAD")
            return None
        try:
            vad = webrtcvad.Vad(max(0, min(3, self.vad_aggressiveness)))
            logger.info("asr_vad_backend", backend="webrtc", aggressiveness=self.vad_aggressiveness)
            return vad
        except Exception as e:  # noqa: BLE001
            logger.warning("webrtcvad init failed, using RMS", error=str(e))
            return None

    def add_audio(self, audio_data: np.ndarray, sample_rate: int = 16000):
        """Add audio data to the processing queue."""
        self.audio_queue.append((audio_data.copy(), sample_rate))

    def run(self):
        """Pull from queue, accumulate, and flush on pauses or backstop.

        All work is wrapped in try/except because ``QThread.run`` silently
        swallows exceptions, which previously left us with a dead worker
        and zero log output when anything in the buffering code raised.
        """
        self.is_running = True
        import time

        last_heartbeat = 0.0

        while self.is_running:
            try:
                # Drain queue into buffer
                while self.audio_queue:
                    audio_data, sr = self.audio_queue.pop(0)
                    self.audio_buffer.append(audio_data)
                    self.sample_rate = sr
                    self.buffer_duration += len(audio_data) / sr

                now = time.time()
                if self.buffer_duration >= self.min_process_duration:
                    if self._should_flush():
                        self._finalize_buffer()
                    elif (
                        self.interim_interval_sec > 0
                        and self.buffer_duration >= self.interim_min_buffer_sec
                        and now - self._last_interim_time >= self.interim_interval_sec
                    ):
                        self._emit_interim()
                        self._last_interim_time = now
                elif now - last_heartbeat >= 3.0 and self.buffer_duration > 0:
                    last_heartbeat = now
                    logger.info(
                        "asr_buffering",
                        buffer_sec=round(self.buffer_duration, 2),
                        median_rms=round(getattr(self, "_last_noise_floor", 0.0), 4),
                        silence_thresh=round(getattr(self, "_last_threshold", 0.0), 4),
                    )
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "ASRWorker loop error (continuing)",
                    error=str(e),
                    error_type=type(e).__name__,
                    buffer_duration=self.buffer_duration,
                    buffer_chunks=len(self.audio_buffer),
                )
                # Drop the buffer to recover rather than loop on the same bad state.
                self.audio_buffer = []
                self.buffer_duration = 0.0

            self.msleep(50)

    def _should_flush(self) -> bool:
        """Return True when it's a good time to transcribe the current buffer."""
        # Backstop: never let the buffer grow unbounded.
        if self.buffer_duration >= self.max_process_duration:
            return True

        # Probe a longer window for noise-floor estimation (2s) but only
        # measure trailing silence against that floor.
        probe_sec = 2.0
        probe_needed = int(probe_sec * self.sample_rate)
        collected: list[np.ndarray] = []
        acc = 0
        for arr in reversed(self.audio_buffer):
            collected.append(arr)
            acc += len(arr)
            if acc >= probe_needed:
                break
        probe = np.concatenate(list(reversed(collected)))[-probe_needed:]
        if self._webrtc_vad is not None:
            return (
                self._trailing_silence_ms_webrtc(probe, self.sample_rate) >= self.silence_flush_ms
            )
        return self._trailing_silence_ms(probe, self.sample_rate) >= self.silence_flush_ms

    def _trailing_silence_ms_webrtc(self, audio: np.ndarray, sr: int) -> int:
        """Measure trailing silence using webrtcvad (10/20/30 ms frames).

        webrtcvad requires 16-bit PCM at 8/16/32/48 kHz. We feed it 30 ms
        frames (so each frame is 480 samples @ 16 kHz). Walks backward and
        returns the count of trailing non-speech frames × 30 ms.
        """
        vad = self._webrtc_vad
        if vad is None or sr not in (8000, 16000, 32000, 48000):
            return self._trailing_silence_ms(audio, sr)
        frame_ms = 30
        frame_samples = sr * frame_ms // 1000
        if audio.dtype == np.float32:
            pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
        else:
            pcm = audio.astype(np.int16, copy=False)
        n_frames = len(pcm) // frame_samples
        if n_frames == 0:
            return 0
        trailing = 0
        for i in range(n_frames - 1, -1, -1):
            chunk = pcm[i * frame_samples : (i + 1) * frame_samples].tobytes()
            try:
                if vad.is_speech(chunk, sr):
                    break
            except Exception:  # noqa: BLE001
                # Wrong frame length etc. -- give up and fall back.
                return self._trailing_silence_ms(audio, sr)
            trailing += 1
        # Remember for logging parity with the RMS path.
        self._last_noise_floor = 0.0
        self._last_threshold = 0.0
        return trailing * frame_ms

    @staticmethod
    def _frame_rms(frame: np.ndarray) -> float:
        """Root-mean-square of an audio frame. Accepts float or int16."""
        if frame.size == 0:
            return 0.0
        if frame.dtype == np.int16:
            f = frame.astype(np.float32) / 32768.0
        else:
            f = frame.astype(np.float32, copy=False)
        return float(np.sqrt(np.mean(f * f)))

    def _trailing_silence_ms(self, audio: np.ndarray, sr: int) -> int:
        """Measure trailing silence (ms) using an adaptive RMS energy gate.

        Computes the noise floor as the minimum framewise RMS across the
        probe, then treats frames as silent when RMS <
        ``max(silence_rms_threshold, noise_floor * silence_noise_multiplier)``.
        This adapts to noisy sources (app loopback with music beds, etc.)
        where a fixed threshold either misses all pauses or triggers on
        speech.
        """
        frame_ms = 20
        frame_samples = max(1, int(sr * frame_ms / 1000))
        n_frames = len(audio) // frame_samples
        if n_frames == 0:
            return 0
        # Vectorised per-frame RMS (much faster than a Python loop).
        trimmed = audio[: n_frames * frame_samples]
        if trimmed.dtype == np.int16:
            trimmed = trimmed.astype(np.float32) / 32768.0
        frames = trimmed.reshape(n_frames, frame_samples).astype(np.float32, copy=False)
        rms_per_frame = np.sqrt(np.mean(frames * frames, axis=1))
        median_rms = float(np.median(rms_per_frame))
        threshold = max(
            self.silence_rms_threshold,
            median_rms * self.silence_relative_ratio,
        )
        self._last_noise_floor = median_rms
        self._last_threshold = threshold
        # Walk backwards from the end, count trailing silent frames.
        trailing = 0
        for i in range(n_frames - 1, -1, -1):
            if rms_per_frame[i] >= threshold:
                break
            trailing += 1
        return trailing * frame_ms

    def _ensure_segment_id(self) -> str:
        """Return the current segment id, creating one if the segment just started."""
        if self._current_segment_id is None:
            import uuid

            self._current_segment_id = str(uuid.uuid4())
        return self._current_segment_id

    def _emit_interim(self):
        """Transcribe the current (growing) buffer and emit as interim.

        Two modes (``qwen_asr.interim_strategy``):

        * ``"full"`` — decode the whole buffer every time (old behaviour).
          Most accurate but cost grows linearly with segment length.
        * ``"window"`` — decode only the last ``interim_window_sec`` seconds.
          Keeps interim cost bounded regardless of segment length. The
          final flush still decodes the entire buffer, so accuracy on the
          committed text is unaffected.

        Does NOT clear the buffer. Reuses the segment id so the UI updates
        a single message in place.
        """
        if not self.audio_buffer:
            return
        audio_data = np.concatenate(self.audio_buffer)
        sr = self.sample_rate

        # Skip interim on silent audio (common in loopback during mute).
        if not self._buffer_has_speech(audio_data, sr):
            return

        # Pick decode window based on strategy.
        if self.interim_strategy == "window" and self.interim_window_sec > 0:
            window_samples = int(self.interim_window_sec * sr)
            if len(audio_data) > window_samples:
                decode_audio = audio_data[-window_samples:]
            else:
                decode_audio = audio_data
        else:
            decode_audio = audio_data

        import time

        segment_id = self._ensure_segment_id()
        t0 = time.time()
        result = self.asr_model.transcribe_audio(decode_audio, sr)
        logger.info(
            "asr_interim",
            audio_sec=round(len(decode_audio) / sr, 2),
            total_buffer_sec=round(len(audio_data) / sr, 2),
            infer_sec=round(time.time() - t0, 3),
            segment_id=segment_id[:8],
            strategy=self.interim_strategy,
        )
        if result and result.text:
            # Override the per-call uuid with our stable segment id and mark non-final.
            result.message_id = segment_id
            result.is_final = False
            self.transcription_ready.emit(result)

    def _finalize_buffer(self):
        """Transcribe the accumulated buffer, emit as final, reset segment."""
        if not self.audio_buffer:
            return

        audio_data = np.concatenate(self.audio_buffer)
        sr = self.sample_rate

        # Decide whether this is a backstop flush (over max_process_duration).
        backstop = self.buffer_duration >= self.max_process_duration

        # Hard-trim to max duration; can only shrink on backstop.
        max_samples = int(self.max_process_duration * sr)
        if len(audio_data) > max_samples:
            audio_data = audio_data[-max_samples:]

        # Skip transcription if the whole buffer is silent.
        if not self._buffer_has_speech(audio_data, sr):
            self.audio_buffer = []
            self.buffer_duration = 0.0
            self._current_segment_id = None
            self._last_interim_time = 0.0
            return

        # Trim leading/trailing silence before decode so the model doesn't
        # spend compute encoding dead air. Keeps a tiny (~60 ms) margin on
        # each side so word-initial plosives and trailing fricatives aren't
        # clipped.
        if self.trim_silence_before_decode:
            audio_data = self._trim_silence(audio_data, sr)
            if len(audio_data) == 0:
                self.audio_buffer = []
                self.buffer_duration = 0.0
                self._current_segment_id = None
                self._last_interim_time = 0.0
                return

        import time

        t0 = time.time()
        result = self.asr_model.transcribe_audio(audio_data, sr)
        segment_id = self._ensure_segment_id()
        logger.info(
            "asr_chunk",
            audio_sec=round(len(audio_data) / sr, 2),
            infer_sec=round(time.time() - t0, 3),
            backstop=backstop,
            segment_id=segment_id[:8],
            median_rms=round(getattr(self, "_last_noise_floor", 0.0), 4),
            silence_thresh=round(getattr(self, "_last_threshold", 0.0), 4),
        )

        if result:
            # Stable segment id so main_window matches interim->final.
            result.message_id = segment_id
            result.is_final = True
            self.transcription_ready.emit(result)

        # Segment is closed -- next interim starts fresh.
        self._current_segment_id = None
        self._last_interim_time = 0.0

        # Reset buffer. On backstop flush, keep a small tail so words spanning
        # the cut are not lost.
        if backstop and self.backstop_tail_sec > 0:
            tail_samples = int(self.backstop_tail_sec * sr)
            tail = (
                audio_data[-tail_samples:]
                if tail_samples > 0
                else np.empty(0, dtype=audio_data.dtype)
            )
            self.audio_buffer = [tail] if len(tail) else []
            self.buffer_duration = len(tail) / sr if len(tail) else 0.0
        else:
            self.audio_buffer = []
            self.buffer_duration = 0.0

    def _buffer_has_speech(self, audio: np.ndarray, sr: int) -> bool:
        """Quick check: does this buffer contain any speech-like audio?

        Uses webrtcvad when available (faster and more accurate than RMS
        on noisy sources). Falls back to the RMS heuristic otherwise.
        Requires >=3 voiced frames (~60-90 ms) to count, to tolerate clicks.
        """
        vad = self._webrtc_vad
        if vad is not None and sr in (8000, 16000, 32000, 48000):
            frame_ms = 30
            frame_samples = sr * frame_ms // 1000
            if audio.dtype == np.float32:
                pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
            else:
                pcm = audio.astype(np.int16, copy=False)
            n_frames = len(pcm) // frame_samples
            voiced = 0
            for i in range(n_frames):
                chunk = pcm[i * frame_samples : (i + 1) * frame_samples].tobytes()
                try:
                    if vad.is_speech(chunk, sr):
                        voiced += 1
                        if voiced >= 3:
                            return True
                except Exception:  # noqa: BLE001
                    break  # fall through to RMS fallback below
            return False

        # RMS fallback (original behaviour).
        frame_ms = 20
        frame_samples = max(1, int(sr * frame_ms / 1000))
        n_frames = len(audio) // frame_samples
        threshold = self.silence_rms_threshold
        voiced = 0
        for i in range(n_frames):
            frame = audio[i * frame_samples : (i + 1) * frame_samples]
            if self._frame_rms(frame) >= threshold:
                voiced += 1
                if voiced >= 3:
                    return True
        return False

    def _trim_silence(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Strip leading/trailing non-speech frames, keep a 60 ms margin.

        Uses webrtcvad @ 30 ms frames when available, else the RMS threshold.
        Returns the audio unchanged if no voiced region is detected (caller
        should have already gated on ``_buffer_has_speech``).
        """
        vad = self._webrtc_vad
        frame_ms = 30 if (vad is not None and sr in (8000, 16000, 32000, 48000)) else 20
        frame_samples = sr * frame_ms // 1000
        if frame_samples <= 0 or len(audio) < frame_samples:
            return audio

        n_frames = len(audio) // frame_samples
        if n_frames == 0:
            return audio

        # Compute voiced mask once.
        if vad is not None and sr in (8000, 16000, 32000, 48000):
            if audio.dtype == np.float32:
                pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
            else:
                pcm = audio.astype(np.int16, copy=False)
            voiced_mask = np.zeros(n_frames, dtype=bool)
            for i in range(n_frames):
                chunk = pcm[i * frame_samples : (i + 1) * frame_samples].tobytes()
                try:
                    voiced_mask[i] = vad.is_speech(chunk, sr)
                except Exception:  # noqa: BLE001
                    # fall back to RMS path for this probe
                    vad = None
                    break
        if vad is None:
            trimmed = audio[: n_frames * frame_samples]
            if trimmed.dtype == np.int16:
                trimmed_f = trimmed.astype(np.float32) / 32768.0
            else:
                trimmed_f = trimmed.astype(np.float32, copy=False)
            frames = trimmed_f.reshape(n_frames, frame_samples)
            rms_per_frame = np.sqrt(np.mean(frames * frames, axis=1))
            median_rms = float(np.median(rms_per_frame))
            threshold = max(self.silence_rms_threshold, median_rms * self.silence_relative_ratio)
            voiced_mask = rms_per_frame >= threshold

        if not voiced_mask.any():
            return audio  # no voiced region detected, leave caller's fallback logic

        first = int(np.argmax(voiced_mask))
        last = n_frames - 1 - int(np.argmax(voiced_mask[::-1]))
        # 60 ms margin so word-initial plosives / trailing fricatives survive.
        margin_frames = max(1, 60 // frame_ms)
        first = max(0, first - margin_frames)
        last = min(n_frames - 1, last + margin_frames)

        start = first * frame_samples
        end = (last + 1) * frame_samples
        trimmed_len = end - start
        if trimmed_len >= len(audio) - frame_samples:
            return audio  # nothing meaningful to trim
        return audio[start:end]

    def stop(self):
        """Stop the worker."""
        self.is_running = False
        self.wait()
