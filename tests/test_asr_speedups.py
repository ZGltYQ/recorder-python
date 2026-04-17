"""Unit tests for Phase 1-3 ASR speed-up changes.

These tests exercise the pure-Python helpers on ASRWorker without
requiring the Qwen3-ASR model to be loaded (which needs a GPU/CUDA and
a 1-2 GB download).
"""

from __future__ import annotations

import numpy as np
import pytest

from src.speech.asr import ASRWorker, Qwen3ASR


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    """Reset the config singleton around every test so we don't leak a
    cached ConfigManager to other test modules (notably the priority-queue
    test which reads ``priority_queue.enabled`` from whatever singleton
    happens to exist)."""
    from src.utils import config as _cfg

    _cfg._config = None
    yield
    _cfg._config = None


@pytest.fixture
def worker(monkeypatch):
    """Build an ASRWorker using the RMS VAD backend (deterministic in tests).

    webrtcvad at its default aggressiveness flags low-level Gaussian noise
    as speech, which makes silence/trim tests flaky. Force RMS so we're
    exercising our own threshold logic.
    """
    from src.utils import config as _cfg

    original_get = _cfg.ConfigManager.get

    def patched_get(self, key, default=None):
        if key == "qwen_asr.vad_backend":
            return "rms"
        return original_get(self, key, default)

    monkeypatch.setattr(_cfg.ConfigManager, "get", patched_get)

    asr = Qwen3ASR(model_size="0.6B")
    w = ASRWorker(asr)
    assert w._webrtc_vad is None, "RMS backend should disable webrtcvad for these tests"
    return w


def _speech_sine(duration_sec: float, sr: int = 16000, freq: float = 200.0) -> np.ndarray:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    audio = 0.3 * np.sin(2 * np.pi * freq * t)
    return audio.astype(np.float32)


def _silence(duration_sec: float, sr: int = 16000) -> np.ndarray:
    """True silence -- zero samples, so RMS threshold gating is reliable."""
    return np.zeros(int(sr * duration_sec), dtype=np.float32)


class TestBufferHasSpeech:
    def test_pure_silence_rejected(self, worker):
        audio = _silence(1.0)
        assert worker._buffer_has_speech(audio, 16000) is False

    def test_strong_signal_accepted(self, worker):
        # 500 ms of tone is plenty for either VAD path.
        audio = _speech_sine(0.5)
        assert worker._buffer_has_speech(audio, 16000) is True

    def test_empty_rejected(self, worker):
        assert worker._buffer_has_speech(np.zeros(0, dtype=np.float32), 16000) is False


class TestTrimSilence:
    def test_trims_leading_and_trailing_silence(self, worker):
        sr = 16000
        audio = np.concatenate([_silence(1.0, sr), _speech_sine(0.5, sr), _silence(1.0, sr)])
        trimmed = worker._trim_silence(audio, sr)
        # Should be shorter than original and significantly shorter than
        # the 2.5 s input (we kept 0.5 s of voice + ~60-90 ms margin each side).
        assert len(trimmed) < len(audio)
        assert len(trimmed) / sr < 1.0
        # And should still contain the voiced segment.
        assert len(trimmed) / sr > 0.4

    def test_all_silence_returns_original(self, worker):
        audio = _silence(1.0)
        trimmed = worker._trim_silence(audio, 16000)
        # If no voiced region, _trim_silence leaves audio untouched so the
        # caller's own silence gating logic decides what to do.
        assert trimmed is audio or len(trimmed) == len(audio)

    def test_short_buffer_unchanged(self, worker):
        # Buffer shorter than one frame -- nothing to trim.
        audio = np.zeros(100, dtype=np.float32)
        trimmed = worker._trim_silence(audio, 16000)
        assert len(trimmed) == len(audio)


class TestInterimStrategy:
    def test_window_strategy_default(self, worker):
        assert worker.interim_strategy in ("window", "full")
        # Default per config is "window"
        assert worker.interim_strategy == "window"
        assert worker.interim_window_sec > 0


class TestResamplerCache:
    def test_resampler_cached_across_calls(self):
        asr = Qwen3ASR(model_size="0.6B")
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        # Two calls at the same rate should hit the cache.
        out1 = asr._resample_audio(audio, 22050, 16000)
        out2 = asr._resample_audio(audio, 22050, 16000)
        assert out1.shape == out2.shape
        assert (22050, 16000) in asr._resampler_cache

    def test_identity_resample_no_cache_entry(self):
        asr = Qwen3ASR(model_size="0.6B")
        audio = np.zeros(100, dtype=np.float32)
        out = asr._resample_audio(audio, 16000, 16000)
        assert out is audio
        assert (16000, 16000) not in asr._resampler_cache


class TestDefaultModelSize:
    def test_default_is_0_6b(self):
        assert Qwen3ASR.DEFAULT_MODEL_SIZE == "0.6B"

    def test_unknown_falls_back(self):
        asr = Qwen3ASR(model_size="nonsense")
        assert asr.model_size == "0.6B"


class TestTrailingSilenceRMS:
    def test_long_trailing_silence_detected(self, worker):
        sr = 16000
        audio = np.concatenate([_speech_sine(0.5, sr), _silence(0.8, sr)])
        ms = worker._trailing_silence_ms(audio, sr)
        # Should be ≥ ~700 ms (we tolerate a frame or two of slack).
        assert ms >= 600, f"expected >=600 ms trailing silence, got {ms}"

    def test_no_trailing_silence(self, worker):
        sr = 16000
        audio = _speech_sine(1.0, sr)
        ms = worker._trailing_silence_ms(audio, sr)
        assert ms == 0

    def test_empty_buffer(self, worker):
        assert worker._trailing_silence_ms(np.zeros(0, dtype=np.float32), 16000) == 0


class TestWebrtcVADBackend:
    """Smoke tests for the webrtcvad wiring.

    We don't test webrtcvad's accuracy (that's upstream's job) -- we just
    verify the worker picks up the optional backend when available and
    falls back cleanly when it isn't.
    """

    def test_webrtc_vad_initialised_by_default(self):
        # Without monkeypatching the config, the default backend is "webrtc"
        # and webrtcvad is in requirements.txt so it must be importable.
        asr = Qwen3ASR(model_size="0.6B")
        w = ASRWorker(asr)
        assert w._webrtc_vad is not None, "webrtcvad should init on default config"

    def test_webrtc_vad_speech_detected(self):
        """_buffer_has_speech should see a loud signal regardless of VAD backend."""
        asr = Qwen3ASR(model_size="0.6B")
        w = ASRWorker(asr)
        audio = _speech_sine(0.5)
        assert w._buffer_has_speech(audio, 16000) is True

    def test_rms_fallback_when_backend_forced_off(self, monkeypatch):
        from src.utils import config as _cfg

        original_get = _cfg.ConfigManager.get

        def patched_get(self, key, default=None):
            if key == "qwen_asr.vad_backend":
                return "rms"
            return original_get(self, key, default)

        monkeypatch.setattr(_cfg.ConfigManager, "get", patched_get)
        asr = Qwen3ASR(model_size="0.6B")
        w = ASRWorker(asr)
        assert w._webrtc_vad is None, "vad_backend=rms must disable webrtcvad"
