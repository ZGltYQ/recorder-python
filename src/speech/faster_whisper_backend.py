"""faster-whisper backend, API-compatible with ``src.speech.asr.Qwen3ASR``.

Both backends expose the same surface that ``TranscriptionManager`` /
``ASRWorker`` rely on:

* signals ``transcription_ready``, ``model_loaded``, ``error``
* ``load_model(...)`` -> bool
* ``transcribe_audio(audio, sample_rate=16000, language=None)``
  -> ``TranscriptionResult | None``
* ``is_ready()`` -> bool
* ``get_model_info()`` -> dict

We deliberately avoid a formal ``typing.Protocol`` / ABC: Qt signals can't
participate in a Protocol and ABCs would force us to re-declare them on
every subclass. Duck typing with a shared result dataclass is enough.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal

from ..utils.config import get_config
from ..utils.logger import get_logger
from .asr import TranscriptionResult

try:
    from faster_whisper import WhisperModel  # type: ignore[import-not-found]

    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    WhisperModel = None  # type: ignore[assignment,misc]

try:
    import ctranslate2  # type: ignore

    CTRANSLATE2_AVAILABLE = True
except ImportError:
    CTRANSLATE2_AVAILABLE = False
    ctranslate2 = None

logger = get_logger(__name__)


# Mapping from our canonical ISO 639-1 codes to the codes faster-whisper expects.
# faster-whisper actually accepts the same codes directly, but we filter through
# a lookup to reject anything unsupported cleanly.
_SUPPORTED_LANGS = {
    "auto": None,  # auto-detect
    "en": "en",
    "ru": "ru",
    "uk": "uk",
}


def _auto_device() -> str:
    """Pick cuda if ctranslate2 reports at least one usable device, else cpu.

    We don't import torch here because the user may have installed
    faster-whisper without torch, and ctranslate2 is the real gate for GPU
    availability. Wrapped in try/except because older CUDA drivers will
    raise RuntimeError from ``get_cuda_device_count``.
    """
    if not CTRANSLATE2_AVAILABLE or ctranslate2 is None:
        return "cpu"
    try:
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception as e:  # noqa: BLE001
        logger.warning("ctranslate2 CUDA probe failed, falling back to CPU", error=str(e))
        return "cpu"


def _auto_compute_type(device: str) -> str:
    """Pick the fastest viable compute_type for the device.

    Order of preference on CUDA:  int8_float16 > float16 > int8 > float32.
    On CPU: int8 > int8_float32 > float32.
    Falls back to ``default`` if we can't enumerate supported types.
    """
    if not CTRANSLATE2_AVAILABLE or ctranslate2 is None:
        return "default"
    try:
        # device_index=0 is valid for both CPU and CUDA. ctranslate2 rejects
        # ``None`` for this parameter, so always pass an int.
        supported = set(ctranslate2.get_supported_compute_types(device, 0))
    except Exception as e:  # noqa: BLE001
        logger.warning("ctranslate2 compute-type probe failed, using default", error=str(e))
        return "default"

    if device == "cuda":
        for ct in ("int8_float16", "float16", "int8_bfloat16", "bfloat16", "int8", "float32"):
            if ct in supported:
                return ct
    else:
        for ct in ("int8", "int8_float32", "float32"):
            if ct in supported:
                return ct
    return "default"


class FasterWhisperASR(QObject):
    """faster-whisper ASR backend (CTranslate2 under the hood).

    Configuration keys (all under ``faster_whisper`` in config.json):

    * ``model_size``  - HF model id or canonical size (``tiny``, ``base``,
      ``small``, ``medium``, ``large-v3``, ``large-v3-turbo``).
    * ``device``      - ``auto`` / ``cuda`` / ``cpu``.
    * ``compute_type``- ``auto`` / ``int8`` / ``int8_float16`` / ``float16`` / ``float32``.
    * ``beam_size``   - greedy=1, default 5.
    * ``vad_filter``  - use faster-whisper's built-in Silero VAD pre-filter.
    * ``vad_min_silence_ms`` - Silero min_silence_duration_ms.
    """

    transcription_ready = Signal(TranscriptionResult)
    model_loaded = Signal(bool)
    error = Signal(str)

    def __init__(self, model_size: str | None = None):
        super().__init__()
        # ``self.model`` is typed as ``object`` because ``WhisperModel`` may be
        # ``None`` at import time (faster-whisper not installed). Consumers
        # must gate on ``self.is_loaded``.
        self.model: object | None = None
        self.device: str = ""
        self.compute_type: str = ""
        self.is_loaded = False

        cfg = get_config()
        self.model_size = model_size or cfg.get("faster_whisper.model_size", "large-v3-turbo")
        self.beam_size = int(cfg.get("faster_whisper.beam_size", 5))
        self.vad_filter = bool(cfg.get("faster_whisper.vad_filter", True))
        self.vad_min_silence_ms = int(cfg.get("faster_whisper.vad_min_silence_ms", 500))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def load_model(self, model_size: str | None = None, device: str | None = None) -> bool:
        """Instantiate the underlying ``WhisperModel``."""
        if not FASTER_WHISPER_AVAILABLE or WhisperModel is None:
            msg = (
                "faster-whisper is not installed. Run `pip install faster-whisper` "
                "or switch the backend to qwen3 in Settings."
            )
            logger.error(msg)
            self.error.emit(msg)
            self.model_loaded.emit(False)
            return False

        cfg = get_config()
        if model_size:
            self.model_size = model_size

        requested_device: str = device or cfg.get("faster_whisper.device", "auto")
        chosen_device = _auto_device() if requested_device == "auto" else requested_device
        self.device = chosen_device

        requested_ct: str = cfg.get("faster_whisper.compute_type", "auto")
        self.compute_type = (
            _auto_compute_type(chosen_device) if requested_ct == "auto" else requested_ct
        )

        # If auto-download is disabled, use local_files_only. faster-whisper
        # looks in the HF cache (~/.cache/huggingface/hub by default).
        local_only = not bool(cfg.get("faster_whisper.auto_download", True))

        try:
            logger.info(
                "Loading faster-whisper model",
                model=self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                local_only=local_only,
            )
            t0 = time.time()
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                local_files_only=local_only,
            )
            logger.info(
                "faster-whisper model loaded",
                load_sec=round(time.time() - t0, 2),
            )

            # Warm up: run a 1 s zero-filled decode so the first real utterance
            # doesn't pay kernel / graph-capture cold-start.
            try:
                if self.model is not None:
                    warm = np.zeros(16000, dtype=np.float32)
                    t0 = time.time()
                    # ``transcribe`` returns (segments_gen, info). We must
                    # exhaust the generator to actually execute the decode.
                    segments_iter, _info = self.model.transcribe(  # type: ignore[attr-defined]
                        warm, beam_size=1, vad_filter=False
                    )
                    list(segments_iter)
                    logger.info("asr_warmup_done", warmup_sec=round(time.time() - t0, 3))
            except Exception as warm_err:  # noqa: BLE001
                logger.warning("asr_warmup_failed", error=str(warm_err))

            self.is_loaded = True
            self.model_loaded.emit(True)
            return True
        except Exception as e:
            logger.error("Failed to load faster-whisper model", error=str(e))
            self.error.emit(f"Failed to load faster-whisper: {e}")
            self.model_loaded.emit(False)
            return False

    def is_ready(self) -> bool:
        return self.is_loaded

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def transcribe_audio(
        self,
        audio_data: np.ndarray | str | Path,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult | None:
        """Run a full decode on ``audio_data`` and return a single result.

        faster-whisper returns a generator of segments; we collect and
        concatenate them. We do **not** try to stream segment-by-segment
        into the UI for interim results -- the existing ``ASRWorker`` layer
        already handles streaming via rolling windows.
        """
        if not self.is_loaded or self.model is None:
            logger.error("faster-whisper model not loaded")
            return None

        try:
            # Normalise audio: float32 mono @ 16 kHz.
            audio_input: np.ndarray | str
            if isinstance(audio_data, np.ndarray):
                arr = audio_data
                if arr.dtype != np.float32:
                    arr = arr.astype(np.float32) / 32768.0
                if arr.ndim > 1:
                    arr = arr.mean(axis=1)
                # faster-whisper expects 16 kHz. capture.py already runs at
                # 16 kHz in practice, but handle mismatches with a minimal
                # linear resample so we don't silently drop audio.
                if sample_rate != 16000:
                    from scipy import signal as _signal  # type: ignore

                    n_out = int(len(arr) * 16000 / sample_rate)
                    arr = np.asarray(_signal.resample(arr, n_out), dtype=np.float32)
                audio_input = arr
            else:
                audio_input = str(audio_data)

            # Resolve language. faster-whisper wants ISO 639-1.
            cfg_lang = get_config().get("stt.language", "auto") if language is None else language
            lang_arg = _SUPPORTED_LANGS.get(cfg_lang, cfg_lang)

            vad_kwargs: dict = {}
            if self.vad_filter:
                vad_kwargs["vad_filter"] = True
                vad_kwargs["vad_parameters"] = dict(min_silence_duration_ms=self.vad_min_silence_ms)

            assert self.model is not None  # gated above via self.is_loaded
            segments_iter, _info = self.model.transcribe(  # type: ignore[attr-defined]
                audio_input,
                language=lang_arg,
                beam_size=self.beam_size,
                **vad_kwargs,
            )
            text = " ".join(seg.text.strip() for seg in segments_iter).strip()

            if not text:
                return None

            return TranscriptionResult(
                text=text,
                timestamp=time.time() * 1000,
                is_final=True,
                message_id=str(uuid.uuid4()),
                confidence=None,
            )
        except Exception as e:
            logger.error("faster-whisper transcribe error", error=str(e))
            self.error.emit(f"Transcription error: {e}")
            return None

    def get_model_info(self) -> dict:
        return {
            "name": f"faster-whisper/{self.model_size}",
            "size": self.model_size,
            "loaded": self.is_loaded,
            "device": self.device,
            "compute_type": self.compute_type,
            "description": "faster-whisper / CTranslate2 backend",
            "backend": "faster-whisper",
        }
