"""Tests for the nested-under-stt config refactor.

Both Qwen3-ASR and faster-whisper are STT backends, so their model configs
live as siblings under ``stt``: ``stt.qwen3`` and ``stt.faster_whisper``.
Shared ASRWorker streaming/VAD knobs live under ``stt.streaming``.

Old config.json files with flat ``qwen_asr`` / ``faster_whisper`` top-level
keys must still load. Code written against the old key strings (via
``config.get("qwen_asr.model_size")``) must still work via transparent
aliasing.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    from src.utils import config as _cfg

    _cfg._config = None
    yield
    _cfg._config = None


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    from src.utils import config as _cfg

    monkeypatch.setattr(_cfg, "user_config_dir", lambda _: str(tmp_path))
    return tmp_path


class TestNewShape:
    """Core invariants of the new nested shape."""

    def test_default_instance_has_nested_sections(self, tmp_config):
        from src.utils.config import ConfigManager

        c = ConfigManager()
        assert c.config.stt.streaming is not None
        assert c.config.stt.qwen3 is not None
        assert c.config.stt.faster_whisper is not None

    def test_saved_file_has_nested_stt(self, tmp_config):
        from src.utils.config import ConfigManager

        c = ConfigManager()
        c.save()

        data = json.loads((tmp_config / "config.json").read_text())
        assert "stt" in data
        assert "streaming" in data["stt"]
        assert "qwen3" in data["stt"]
        assert "faster_whisper" in data["stt"]
        # The legacy top-level sections must NOT be emitted.
        assert "qwen_asr" not in data
        assert "faster_whisper" not in data

    def test_new_canonical_paths_work(self, tmp_config):
        from src.utils.config import ConfigManager

        c = ConfigManager()
        assert c.get("stt.backend") == "qwen3"
        assert c.get("stt.qwen3.model_size") == "0.6B"
        assert c.get("stt.faster_whisper.model_size") == "large-v3-turbo"
        assert c.get("stt.streaming.min_chunk_sec") == 2.0
        assert c.get("stt.streaming.vad_backend") == "webrtc"


class TestLegacyAliasing:
    """Old key strings must keep working in every way old code uses them."""

    def test_get_alias_routes_qwen_streaming_field(self, tmp_config):
        from src.utils.config import ConfigManager

        c = ConfigManager()
        # Streaming knob lived under qwen_asr.* in old code.
        assert c.get("qwen_asr.min_chunk_sec") == c.get("stt.streaming.min_chunk_sec")
        assert c.get("qwen_asr.vad_backend") == c.get("stt.streaming.vad_backend")
        assert c.get("qwen_asr.interim_strategy") == c.get("stt.streaming.interim_strategy")

    def test_get_alias_routes_qwen_model_field(self, tmp_config):
        from src.utils.config import ConfigManager

        c = ConfigManager()
        assert c.get("qwen_asr.model_size") == c.get("stt.qwen3.model_size")
        assert c.get("qwen_asr.auto_download") == c.get("stt.qwen3.auto_download")

    def test_get_alias_routes_faster_whisper(self, tmp_config):
        from src.utils.config import ConfigManager

        c = ConfigManager()
        assert c.get("faster_whisper.model_size") == c.get("stt.faster_whisper.model_size")
        assert c.get("faster_whisper.compute_type") == c.get("stt.faster_whisper.compute_type")
        assert c.get("faster_whisper.vad_filter") == c.get("stt.faster_whisper.vad_filter")

    def test_set_alias_updates_nested_path(self, tmp_config):
        from src.utils.config import ConfigManager

        c = ConfigManager()
        c.set("qwen_asr.model_size", "1.7B")
        assert c.config.stt.qwen3.model_size == "1.7B"
        assert c.get("stt.qwen3.model_size") == "1.7B"

        c.set("qwen_asr.min_chunk_sec", 3.0)
        assert c.config.stt.streaming.min_chunk_sec == 3.0
        assert c.get("stt.streaming.min_chunk_sec") == 3.0

        c.set("faster_whisper.compute_type", "int8")
        assert c.config.stt.faster_whisper.compute_type == "int8"


class TestBackwardCompatLoad:
    """Old config.json files with the flat shape must still load correctly."""

    def test_old_flat_shape_loads(self, tmp_config):
        # Write an old-style config.json.
        old_data = {
            "stt": {
                "language": "ru",
                "model_size": "small",
                "device": "auto",
                "sample_rate": 16000,
            },
            "qwen_asr": {
                "model_size": "1.7B",
                "auto_download": True,
                "cache_dir": "",
                "min_chunk_sec": 2.5,
                "max_chunk_sec": 10.0,
                "silence_flush_ms": 250,
                "interim_strategy": "full",
                "vad_backend": "rms",
                "vad_aggressiveness": 3,
            },
            "faster_whisper": {
                "model_size": "small",
                "compute_type": "int8",
                "device": "cpu",
                "beam_size": 1,
                "vad_filter": False,
                "vad_min_silence_ms": 700,
                "auto_download": True,
            },
        }
        (tmp_config / "config.json").write_text(json.dumps(old_data))

        from src.utils.config import ConfigManager

        c = ConfigManager()

        # Streaming fields migrated to stt.streaming.
        assert c.get("stt.streaming.min_chunk_sec") == 2.5
        assert c.get("stt.streaming.max_chunk_sec") == 10.0
        assert c.get("stt.streaming.silence_flush_ms") == 250
        assert c.get("stt.streaming.interim_strategy") == "full"
        assert c.get("stt.streaming.vad_backend") == "rms"
        assert c.get("stt.streaming.vad_aggressiveness") == 3

        # Qwen-specific fields kept under stt.qwen3.
        assert c.get("stt.qwen3.model_size") == "1.7B"
        assert c.get("stt.qwen3.auto_download") is True

        # faster_whisper top-level moved under stt.faster_whisper.
        assert c.get("stt.faster_whisper.model_size") == "small"
        assert c.get("stt.faster_whisper.compute_type") == "int8"
        assert c.get("stt.faster_whisper.vad_filter") is False

    def test_old_keys_still_readable_on_old_config(self, tmp_config):
        old_data = {
            "stt": {
                "language": "ru",
                "model_size": "small",
                "device": "auto",
                "sample_rate": 16000,
            },
            "qwen_asr": {"model_size": "1.7B", "min_chunk_sec": 2.5, "auto_download": False},
            "faster_whisper": {
                "model_size": "small",
                "compute_type": "int8",
                "device": "cpu",
                "beam_size": 1,
                "vad_filter": False,
                "vad_min_silence_ms": 500,
                "auto_download": True,
            },
        }
        (tmp_config / "config.json").write_text(json.dumps(old_data))

        from src.utils.config import ConfigManager

        c = ConfigManager()
        # Code that reads via old keys still works.
        assert c.get("qwen_asr.model_size") == "1.7B"
        assert c.get("qwen_asr.min_chunk_sec") == 2.5
        assert c.get("qwen_asr.auto_download") is False
        assert c.get("faster_whisper.compute_type") == "int8"

    def test_roundtrip_old_to_new_on_save(self, tmp_config):
        """Loading an old-shape config.json and re-saving produces the new shape."""
        old_data = {
            "stt": {
                "language": "en",
                "model_size": "small",
                "device": "auto",
                "sample_rate": 16000,
            },
            "qwen_asr": {
                "model_size": "0.6B",
                "min_chunk_sec": 3.0,
            },
        }
        cfg_file = tmp_config / "config.json"
        cfg_file.write_text(json.dumps(old_data))

        from src.utils.config import ConfigManager

        c = ConfigManager()
        c.save()

        new_data = json.loads(cfg_file.read_text())
        # Old keys gone.
        assert "qwen_asr" not in new_data
        # New nested shape.
        assert new_data["stt"]["qwen3"]["model_size"] == "0.6B"
        assert new_data["stt"]["streaming"]["min_chunk_sec"] == 3.0


class TestNewShapeIsSelfConsistent:
    def test_new_shape_roundtrips(self, tmp_config):
        """Saving a fresh default config and loading it back must produce
        the same values everywhere."""
        from src.utils import config as _cfg
        from src.utils.config import ConfigManager

        c = ConfigManager()
        c.set("stt.qwen3.model_size", "1.7B")
        c.set("stt.streaming.interim_window_sec", 6.0)
        c.set("stt.faster_whisper.beam_size", 1)

        # Force a fresh reload from disk.
        _cfg._config = None
        c2 = ConfigManager()
        assert c2.get("stt.qwen3.model_size") == "1.7B"
        assert c2.get("stt.streaming.interim_window_sec") == 6.0
        assert c2.get("stt.faster_whisper.beam_size") == 1

        # Legacy aliases still resolve.
        assert c2.get("qwen_asr.model_size") == "1.7B"
        assert c2.get("qwen_asr.interim_window_sec") == 6.0
        assert c2.get("faster_whisper.beam_size") == 1
