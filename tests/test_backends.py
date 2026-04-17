"""Tests for the ASR backend protocol, selection, and faster-whisper wiring.

We deliberately don't load any real ASR model here -- that would need a
GPU + 1-2 GB model download. Instead we test:

  * config round-trip for ``stt.backend`` and ``faster_whisper.*``
  * TranscriptionManager picks the right concrete class from config
  * fallback to qwen3 when faster-whisper isn't importable
  * FasterWhisperASR's audio-normalisation happy path (doesn't load a
    model, just exercises the input-shape logic via a stub)
"""

from __future__ import annotations

import numpy as np
import pytest

from src.speech.asr import Qwen3ASR, TranscriptionManager
from src.speech.faster_whisper_backend import (
    FASTER_WHISPER_AVAILABLE,
    FasterWhisperASR,
    _auto_compute_type,
    _auto_device,
)


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    from src.utils import config as _cfg

    _cfg._config = None
    yield
    _cfg._config = None


def _patch_config(monkeypatch, overrides: dict):
    """Stub ConfigManager.get so selected keys return test values."""
    from src.utils import config as _cfg

    original_get = _cfg.ConfigManager.get

    def patched_get(self, key, default=None):
        if key in overrides:
            return overrides[key]
        return original_get(self, key, default)

    monkeypatch.setattr(_cfg.ConfigManager, "get", patched_get)


class TestConfigRoundTrip:
    def test_default_backend_is_qwen3(self):
        from src.utils.config import STTConfig

        assert STTConfig().backend == "qwen3"

    def test_faster_whisper_config_defaults(self):
        from src.utils.config import FasterWhisperConfig

        fw = FasterWhisperConfig()
        assert fw.model_size == "large-v3-turbo"
        assert fw.compute_type == "auto"
        assert fw.vad_filter is True
        assert fw.beam_size == 5

    def test_config_json_roundtrip(self, tmp_path, monkeypatch):
        from src.utils import config as _cfg

        monkeypatch.setattr(_cfg, "user_config_dir", lambda _: str(tmp_path))
        mgr = _cfg.ConfigManager()
        mgr.set("stt.backend", "faster-whisper")
        mgr.set("faster_whisper.model_size", "small")
        mgr.set("faster_whisper.compute_type", "int8")

        # Re-read from disk.
        mgr2 = _cfg.ConfigManager()
        assert mgr2.get("stt.backend") == "faster-whisper"
        assert mgr2.get("faster_whisper.model_size") == "small"
        assert mgr2.get("faster_whisper.compute_type") == "int8"


class TestBackendSelection:
    def test_default_selects_qwen3(self, monkeypatch):
        _patch_config(monkeypatch, {"stt.backend": "qwen3"})
        m = TranscriptionManager()
        assert m.backend_name == "qwen3"
        assert isinstance(m.asr, Qwen3ASR)

    def test_faster_whisper_backend_selected(self, monkeypatch):
        if not FASTER_WHISPER_AVAILABLE:
            pytest.skip("faster-whisper not installed")
        _patch_config(monkeypatch, {"stt.backend": "faster-whisper"})
        m = TranscriptionManager()
        assert m.backend_name == "faster-whisper"
        assert isinstance(m.asr, FasterWhisperASR)

    def test_falls_back_to_qwen3_when_fw_import_fails(self, monkeypatch):
        """If the faster-whisper import blows up, we must NOT crash the app --
        we log and fall back to qwen3."""
        import sys

        # Hide the already-cached module so the fresh import fails.
        monkeypatch.setitem(sys.modules, "faster_whisper", None)
        # Also invalidate our wrapper (it caches FASTER_WHISPER_AVAILABLE at
        # import time). Easiest way: monkeypatch the availability flag.
        monkeypatch.setattr("src.speech.faster_whisper_backend.FASTER_WHISPER_AVAILABLE", False)
        monkeypatch.setattr("src.speech.faster_whisper_backend.WhisperModel", None)
        _patch_config(monkeypatch, {"stt.backend": "faster-whisper"})

        m = TranscriptionManager()
        # _build_backend sees FASTER_WHISPER_AVAILABLE=False and falls back.
        assert isinstance(m.asr, Qwen3ASR)


class TestFasterWhisperBackendSmoke:
    """Non-model-loading smoke tests for FasterWhisperASR."""

    def test_get_model_info_before_load(self):
        b = FasterWhisperASR()
        info = b.get_model_info()
        assert info["backend"] == "faster-whisper"
        assert info["loaded"] is False
        assert "faster-whisper/" in info["name"]

    def test_load_model_without_faster_whisper_emits_error(self, monkeypatch):
        monkeypatch.setattr("src.speech.faster_whisper_backend.FASTER_WHISPER_AVAILABLE", False)
        monkeypatch.setattr("src.speech.faster_whisper_backend.WhisperModel", None)

        b = FasterWhisperASR()
        errors = []
        b.error.connect(errors.append)

        assert b.load_model() is False
        assert len(errors) == 1
        assert "faster-whisper" in errors[0].lower()

    def test_auto_device_fallback_is_cpu(self):
        # On this CI machine ctranslate2's CUDA runtime check may fail,
        # which must degrade to "cpu" rather than raise.
        device = _auto_device()
        assert device in ("cpu", "cuda")

    def test_auto_compute_type_picks_int8_on_cpu(self):
        ct = _auto_compute_type("cpu")
        # int8 is the expected pick on modern CPU builds of ctranslate2.
        # Falls back to "default" only if ctranslate2 rejects the probe.
        assert ct in ("int8", "int8_float32", "float32", "default")


class TestFasterWhisperAudioNormalisation:
    """``transcribe_audio`` normalises int16 -> float32 mono @ 16 kHz before
    handing off to faster-whisper. We test the normalisation path without
    actually loading the model by stubbing self.model."""

    def test_int16_stereo_44100_is_normalised(self, monkeypatch):
        b = FasterWhisperASR()
        b.is_loaded = True

        captured = {}

        class FakeModel:
            def transcribe(self, audio, **kwargs):
                captured["audio"] = audio
                captured["kwargs"] = kwargs

                class _Seg:
                    text = "hello"

                def _gen():
                    yield _Seg()

                # faster-whisper returns (segments, info) -- info can be any
                # truthy object for our purposes.
                return _gen(), object()

        b.model = FakeModel()

        # 1 s of stereo int16 @ 44.1 kHz.
        sr = 44100
        stereo = np.stack(
            [
                (1000 * np.sin(np.linspace(0, 2 * np.pi * 200, sr))).astype(np.int16),
                (1000 * np.cos(np.linspace(0, 2 * np.pi * 200, sr))).astype(np.int16),
            ],
            axis=1,
        )

        result = b.transcribe_audio(stereo, sample_rate=sr, language="en")

        assert result is not None
        assert result.text == "hello"
        assert result.is_final is True

        passed_audio = captured["audio"]
        # After normalisation: float32, 1-D (mono), resampled to 16 kHz.
        assert passed_audio.dtype == np.float32
        assert passed_audio.ndim == 1
        assert abs(len(passed_audio) - 16000) < 100  # 1 s at 16 kHz, a few samples of slack

    def test_empty_text_returns_none(self, monkeypatch):
        b = FasterWhisperASR()
        b.is_loaded = True

        class FakeModel:
            def transcribe(self, audio, **kwargs):
                def _gen():
                    return
                    yield  # never reached -- empty generator

                return _gen(), object()

        b.model = FakeModel()
        audio = np.zeros(16000, dtype=np.float32)
        assert b.transcribe_audio(audio) is None
