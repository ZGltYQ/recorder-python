"""Configuration management for the Audio Recorder application."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from appdirs import user_config_dir

# ---------------------------------------------------------------------------
# STT / ASR configuration
#
# Both Qwen3-ASR and faster-whisper are STT backends, so their model configs
# are nested SIBLINGS under ``stt``. Streaming/VAD knobs that apply to every
# backend live under ``stt.streaming``.
#
# On disk (config.json):
#
#     stt:
#       language, backend, ...
#       streaming: { ... shared streaming/VAD knobs ... }
#       qwen3:          { model_size, auto_download, cache_dir }
#       faster_whisper: { model_size, compute_type, device, beam_size, ... }
#
# The old flat ``qwen_asr.*`` and ``faster_whisper.*`` top-level sections are
# still READ on load (see ``ConfigManager._from_dict``) and the old key
# strings (``config.get("qwen_asr.model_size")``) still work via alias in
# ``ConfigManager.get`` / ``set``. Existing code and existing config.json
# files keep working without modification; saves shift to the new shape.
# ---------------------------------------------------------------------------


@dataclass
class ASRStreamingConfig:
    """Backend-agnostic streaming / VAD knobs used by ``ASRWorker``.

    These apply regardless of which backend (Qwen3 / faster-whisper / future)
    is active: they govern how we slice incoming audio into segments, when
    to emit interims vs finals, and which VAD is used for silence detection.
    """

    # Minimum buffered audio before a flush (finalization) is allowed.
    min_chunk_sec: float = 2.0
    # Hard backstop: finalize even without a pause past this many seconds.
    max_chunk_sec: float = 12.0
    # Trailing silence (ms) that counts as a natural pause.
    silence_flush_ms: int = 300
    # Interim ("streaming") emit cadence. 0 disables interim emits.
    interim_interval_sec: float = 1.5
    # Don't emit interims until the buffer has at least this many seconds.
    interim_min_buffer_sec: float = 1.2
    # Tail audio (sec) carried into next segment when we backstop-flush.
    backstop_tail_sec: float = 0.5
    # RMS silence threshold for the legacy VAD (floor value).
    silence_rms_threshold: float = 0.005
    # Adaptive multiplier on the median RMS noise floor.
    silence_relative_ratio: float = 0.35
    # VAD backend. "webrtc" uses webrtcvad (falls back to "rms" on import
    # failure or broken wheel); "rms" forces the legacy path.
    vad_backend: str = "webrtc"
    # webrtcvad aggressiveness 0-3 (higher = cuts more).
    vad_aggressiveness: int = 2
    # Interim decoding strategy. "window" decodes only the last
    # ``interim_window_sec`` seconds (3-6x cheaper on long utterances);
    # "full" re-decodes the entire buffer every time (old behaviour).
    interim_strategy: str = "window"
    interim_window_sec: float = 4.0
    # Trim leading/trailing silence before the final decode (with a 60 ms
    # margin so plosives/fricatives aren't clipped).
    trim_silence_before_decode: bool = True


@dataclass
class Qwen3ModelConfig:
    """Qwen3-ASR-specific model settings.

    Fields that used to live at the top level under ``qwen_asr`` and
    weren't actually backend-specific now live in ``ASRStreamingConfig``.
    """

    # "0.6B" is the faster default (~2-3x speed-up vs 1.7B); 1.7B is slightly
    # more accurate on multilingual. Existing installs keep whatever was
    # saved in their config.json.
    model_size: str = "0.6B"
    auto_download: bool = True
    cache_dir: str = ""


@dataclass
class FasterWhisperConfig:
    """faster-whisper-specific model settings.

    See https://github.com/SYSTRAN/faster-whisper for model-size / compute-type
    trade-offs. ``large-v3-turbo`` is multilingual and ~4-8x faster than vanilla
    large-v3 while keeping most of the quality. ``compute_type=auto`` picks
    ``int8_float16`` on CUDA, ``int8`` on CPU.
    """

    model_size: str = "large-v3-turbo"
    compute_type: str = "auto"
    device: str = "auto"
    beam_size: int = 5
    # faster-whisper's own built-in Silero VAD (separate from the cross-backend
    # ``ASRStreamingConfig.vad_backend``).
    vad_filter: bool = True
    vad_min_silence_ms: int = 500
    auto_download: bool = True


@dataclass
class STTConfig:
    """Speech-to-text configuration.

    Holds the active backend plus per-backend and shared streaming configs.
    """

    language: str = "auto"
    # Kept for historical back-compat with older config.json files. No code
    # actually reads it today -- real model size lives on the per-backend
    # section (``stt.qwen3.model_size`` / ``stt.faster_whisper.model_size``).
    model_size: str = "small"
    device: str = "auto"  # auto, cpu, cuda
    sample_rate: int = 16000
    # Active ASR backend. ``qwen3`` is the bundled default; ``faster-whisper``
    # is optional and pulls in ``faster-whisper`` / ``ctranslate2`` wheels.
    backend: str = "qwen3"

    # Nested sub-configs. Use ``None`` here + fill in ``__post_init__`` to
    # match the existing None-defaults pattern used elsewhere in this module.
    streaming: "ASRStreamingConfig | None" = None
    qwen3: "Qwen3ModelConfig | None" = None
    faster_whisper: "FasterWhisperConfig | None" = None

    def __post_init__(self) -> None:
        if self.streaming is None:
            self.streaming = ASRStreamingConfig()
        if self.qwen3 is None:
            self.qwen3 = Qwen3ModelConfig()
        if self.faster_whisper is None:
            self.faster_whisper = FasterWhisperConfig()


@dataclass
class OpenRouterConfig:
    """OpenRouter API configuration."""

    api_key: str = ""
    model: str = "anthropic/claude-3.5-sonnet"
    temperature: float = 0.7
    max_tokens: int = 1000


@dataclass
class AudioConfig:
    """Audio capture configuration."""

    sample_rate: int = 16000
    channels: int = 1
    # parec read granularity. Short chunks let silence-flush latency be
    # governed by qwen_asr.silence_flush_ms instead of by this value.
    # Previously 0.5 s (unused in code -- capture used a hard-coded 2.0 s),
    # now honoured and defaulted to 0.1 s.
    chunk_duration: float = 0.1  # seconds
    format: str = "s16le"


@dataclass
class DiarizationConfig:
    """Speaker diarization configuration."""

    enabled: bool = True
    min_speakers: int = 1
    max_speakers: int = 6
    threshold: float = 0.5


@dataclass
class PriorityQueueConfig:
    """Priority queue configuration."""

    enabled: bool = True
    aging_interval: int = 30  # seconds between aging increments
    aging_factor: float = 0.5  # how much priority increases per aging interval
    max_age: int = 10  # maximum aging steps before forced processing
    max_concurrent: int = 2  # maximum concurrent AI API calls


@dataclass
class LocalLLMConfig:
    """Local LLM API configuration."""

    enabled: bool = False
    base_url: str = "http://localhost:8000/v1"  # OpenAI-compatible endpoint
    model_name: str = "local-model"
    api_key: str = ""  # Optional for local LLMs
    timeout: int = 300  # seconds, minimum 300s for cold-start models


@dataclass
class ScreenshotConfig:
    """Screenshot capture configuration."""

    enabled: bool = False  # Screenshot mode off by default
    interval: int = 30  # seconds, 5-300 range
    max_count: int = 50  # circular buffer size


@dataclass
class AppConfig:
    """Main application configuration.

    Note: ASR-related configs (Qwen3, faster-whisper, streaming/VAD) live
    UNDER ``stt`` (see ``STTConfig``). They used to be top-level keys
    (``qwen_asr``, ``faster_whisper``) and old config.json files with that
    shape still load correctly via ``ConfigManager._from_dict``; saves always
    emit the new nested shape.
    """

    stt: STTConfig = None
    openrouter: OpenRouterConfig = None
    audio: AudioConfig = None
    diarization: DiarizationConfig = None
    priority_queue: PriorityQueueConfig = None
    local_llm: LocalLLMConfig = None
    screenshot: ScreenshotConfig = None
    theme: str = "system"  # system, light, dark
    first_run: bool = True
    provider: str = "openrouter"  # LLM provider: "openrouter" or "local"

    def __post_init__(self):
        if self.stt is None:
            self.stt = STTConfig()
        if self.openrouter is None:
            self.openrouter = OpenRouterConfig()
        if self.audio is None:
            self.audio = AudioConfig()
        if self.diarization is None:
            self.diarization = DiarizationConfig()
        if self.priority_queue is None:
            self.priority_queue = PriorityQueueConfig()
        if self.local_llm is None:
            self.local_llm = LocalLLMConfig()
        if self.screenshot is None:
            self.screenshot = ScreenshotConfig()


class ConfigManager:
    """Manages application configuration persistence."""

    def __init__(self, app_name: str = "recorder-python"):
        self.app_name = app_name
        self.config_dir = Path(user_config_dir(app_name))
        self.config_file = self.config_dir / "config.json"
        self.config = AppConfig()

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Load existing config or create default
        self.load()

    def load(self) -> None:
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    data = json.load(f)
                    self._from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error loading config: {e}. Using defaults.")
                self.config = AppConfig()
                self.save()

    def save(self) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self._to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    # ------------------------------------------------------------------
    # Legacy key-name migration
    #
    # The old config.json had ``qwen_asr`` and ``faster_whisper`` as
    # top-level keys. The Qwen section in particular was overloaded with
    # streaming/VAD knobs that weren't Qwen-specific at all. The fields below
    # document which old ``qwen_asr.<field>`` names now live under
    # ``stt.streaming.<field>`` versus which stayed with the backend under
    # ``stt.qwen3.<field>``.
    # ------------------------------------------------------------------

    _STREAMING_FIELDS = frozenset(
        {
            "min_chunk_sec",
            "max_chunk_sec",
            "silence_flush_ms",
            "interim_interval_sec",
            "interim_min_buffer_sec",
            "backstop_tail_sec",
            "silence_rms_threshold",
            "silence_relative_ratio",
            "vad_backend",
            "vad_aggressiveness",
            "interim_strategy",
            "interim_window_sec",
            "trim_silence_before_decode",
        }
    )

    # Fields that remain Qwen-specific under the new ``stt.qwen3`` section.
    _QWEN3_FIELDS = frozenset({"model_size", "auto_download", "cache_dir"})

    @classmethod
    def _alias_legacy_key(cls, key: str) -> str:
        """Translate a legacy flat key to the new nested path.

        ``qwen_asr.model_size`` -> ``stt.qwen3.model_size``
        ``qwen_asr.min_chunk_sec`` -> ``stt.streaming.min_chunk_sec``
        ``faster_whisper.compute_type`` -> ``stt.faster_whisper.compute_type``

        Unknown keys are returned unchanged.
        """
        if key.startswith("qwen_asr."):
            field = key[len("qwen_asr.") :]
            if field in cls._STREAMING_FIELDS:
                return f"stt.streaming.{field}"
            if field in cls._QWEN3_FIELDS:
                return f"stt.qwen3.{field}"
            # Unknown field under qwen_asr.* -- route to qwen3 as the least
            # surprising fallback.
            return f"stt.qwen3.{field}"
        if key.startswith("faster_whisper."):
            return f"stt.faster_whisper.{key[len('faster_whisper.') :]}"
        return key

    def _to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary (new nested shape only)."""
        return {
            "stt": asdict(self.config.stt),
            "openrouter": asdict(self.config.openrouter),
            "audio": asdict(self.config.audio),
            "diarization": asdict(self.config.diarization),
            "priority_queue": asdict(self.config.priority_queue),
            "local_llm": asdict(self.config.local_llm),
            "screenshot": asdict(self.config.screenshot),
            "theme": self.config.theme,
            "first_run": self.config.first_run,
            "provider": self.config.provider,
        }

    def _from_dict(self, data: dict[str, Any]) -> None:
        """Load config from dictionary (accepts old flat shape OR new nested)."""
        # ---- STT (new nested form) ----
        if "stt" in data:
            stt_data = dict(data["stt"])  # copy so we can pop
            streaming_data = stt_data.pop("streaming", None)
            qwen3_data = stt_data.pop("qwen3", None)
            fw_data = stt_data.pop("faster_whisper", None)
            self.config.stt = STTConfig(**stt_data)
            if streaming_data:
                self.config.stt.streaming = ASRStreamingConfig(**streaming_data)
            if qwen3_data:
                self.config.stt.qwen3 = Qwen3ModelConfig(**qwen3_data)
            if fw_data:
                self.config.stt.faster_whisper = FasterWhisperConfig(**fw_data)

        # ---- Back-compat: flat top-level qwen_asr -> split between streaming
        # and qwen3 sub-configs. Only fields not already set by the nested
        # form above are moved; the nested form wins if both are present.
        if "qwen_asr" in data:
            qwen_data = dict(data["qwen_asr"])
            streaming = self.config.stt.streaming
            qwen3 = self.config.stt.qwen3
            for k, v in qwen_data.items():
                if k in ConfigManager._STREAMING_FIELDS and hasattr(streaming, k):
                    setattr(streaming, k, v)
                elif k in ConfigManager._QWEN3_FIELDS and hasattr(qwen3, k):
                    setattr(qwen3, k, v)

        # ---- Back-compat: flat top-level faster_whisper.
        # Honour the old top-level section only if the new nested form
        # didn't already provide one under ``stt.faster_whisper``.
        has_nested_fw = isinstance(data.get("stt"), dict) and "faster_whisper" in data["stt"]
        if "faster_whisper" in data and not has_nested_fw:
            self.config.stt.faster_whisper = FasterWhisperConfig(**data["faster_whisper"])

        if "openrouter" in data:
            self.config.openrouter = OpenRouterConfig(**data["openrouter"])
        if "audio" in data:
            self.config.audio = AudioConfig(**data["audio"])
        if "diarization" in data:
            self.config.diarization = DiarizationConfig(**data["diarization"])
        if "priority_queue" in data:
            self.config.priority_queue = PriorityQueueConfig(**data["priority_queue"])
        if "local_llm" in data:
            self.config.local_llm = LocalLLMConfig(**data["local_llm"])
        if "screenshot" in data:
            self.config.screenshot = ScreenshotConfig(**data["screenshot"])
        if "theme" in data:
            self.config.theme = data["theme"]
        if "first_run" in data:
            self.config.first_run = data["first_run"]
        if "provider" in data:
            self.config.provider = data["provider"]

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key path (e.g. ``stt.language``).

        Legacy flat keys (``qwen_asr.*`` / ``faster_whisper.*``) are
        translated transparently so existing callers keep working.
        """
        key = ConfigManager._alias_legacy_key(key)
        keys = key.split(".")
        value: Any = self.config
        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by key path.

        Legacy flat keys are translated (see ``get``).
        """
        key = ConfigManager._alias_legacy_key(key)
        keys = key.split(".")
        target: Any = self.config
        for k in keys[:-1]:
            if hasattr(target, k):
                target = getattr(target, k)
            else:
                return
        if hasattr(target, keys[-1]):
            setattr(target, keys[-1], value)
            self.save()

    def get_models_dir(self) -> Path:
        """Get the directory for ASR models."""
        models_dir = self.config_dir / "models"
        models_dir.mkdir(exist_ok=True)
        return models_dir

    def get_data_dir(self) -> Path:
        """Get the directory for application data."""
        data_dir = self.config_dir / "data"
        data_dir.mkdir(exist_ok=True)
        return data_dir


# Global config instance
_config: ConfigManager | None = None


def get_config() -> ConfigManager:
    """Get the global configuration manager."""
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config
