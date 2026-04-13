"""Configuration management for the Audio Recorder application."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict
from appdirs import user_config_dir


@dataclass
class STTConfig:
    """Speech-to-text configuration."""

    language: str = "auto"
    model_size: str = "small"  # small, medium, large
    device: str = "auto"  # auto, cpu, cuda
    sample_rate: int = 16000


@dataclass
class QwenASRConfig:
    """Qwen3-ASR model configuration."""

    model_size: str = "1.7B"  # "0.6B" or "1.7B"
    auto_download: bool = True  # Automatically download model if not present
    cache_dir: str = ""  # Custom cache directory (empty = default)


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
    chunk_duration: float = 0.5  # seconds
    format: str = "s16le"


@dataclass
class DiarizationConfig:
    """Speaker diarization configuration."""

    enabled: bool = True
    min_speakers: int = 1
    max_speakers: int = 6
    threshold: float = 0.5


@dataclass
class AppConfig:
    """Main application configuration."""

    stt: STTConfig = None
    qwen_asr: QwenASRConfig = None
    openrouter: OpenRouterConfig = None
    audio: AudioConfig = None
    diarization: DiarizationConfig = None
    theme: str = "system"  # system, light, dark
    first_run: bool = True

    def __post_init__(self):
        if self.stt is None:
            self.stt = STTConfig()
        if self.qwen_asr is None:
            self.qwen_asr = QwenASRConfig()
        if self.openrouter is None:
            self.openrouter = OpenRouterConfig()
        if self.audio is None:
            self.audio = AudioConfig()
        if self.diarization is None:
            self.diarization = DiarizationConfig()


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
                with open(self.config_file, "r") as f:
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

    def _to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "stt": asdict(self.config.stt),
            "qwen_asr": asdict(self.config.qwen_asr),
            "openrouter": asdict(self.config.openrouter),
            "audio": asdict(self.config.audio),
            "diarization": asdict(self.config.diarization),
            "theme": self.config.theme,
            "first_run": self.config.first_run,
        }

    def _from_dict(self, data: Dict[str, Any]) -> None:
        """Load config from dictionary."""
        if "stt" in data:
            self.config.stt = STTConfig(**data["stt"])
        if "qwen_asr" in data:
            self.config.qwen_asr = QwenASRConfig(**data["qwen_asr"])
        if "openrouter" in data:
            self.config.openrouter = OpenRouterConfig(**data["openrouter"])
        if "audio" in data:
            self.config.audio = AudioConfig(**data["audio"])
        if "diarization" in data:
            self.config.diarization = DiarizationConfig(**data["diarization"])
        if "theme" in data:
            self.config.theme = data["theme"]
        if "first_run" in data:
            self.config.first_run = data["first_run"]

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key path (e.g., 'stt.language')."""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by key path."""
        keys = key.split(".")
        target = self.config
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
_config: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global configuration manager."""
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config
