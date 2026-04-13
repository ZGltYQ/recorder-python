"""Qwen3-ASR (Automatic Speech Recognition) module."""

import io
import wave
from dataclasses import dataclass
from typing import Callable, List, Optional, Union
from pathlib import Path
import numpy as np
from PySide6.QtCore import QObject, Signal, QThread

from ..utils.logger import get_logger
from ..utils.config import get_config

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
    speaker: Optional[str] = None
    message_id: Optional[str] = None
    confidence: Optional[float] = None


class Qwen3ASR(QObject):
    """Qwen3 Automatic Speech Recognition."""

    # Signals
    transcription_ready = Signal(TranscriptionResult)
    model_loaded = Signal(bool)
    error = Signal(str)

    # Available model sizes
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

    def __init__(self, model_size: str = "1.7B"):
        super().__init__()
        self.model = None
        self.device = None
        self.is_loaded = False
        self.model_size = model_size if model_size in self.AVAILABLE_MODELS else "1.7B"
        self.model_name = self.AVAILABLE_MODELS[self.model_size]["name"]
        self.model_info = self.AVAILABLE_MODELS[self.model_size]

    def load_model(self, model_size: Optional[str] = None, device: str = "auto") -> bool:
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

            self.model = Qwen3ASRModel.from_pretrained(
                self.model_name,
                dtype=torch_dtype,
                device_map=self.device if self.device == "cuda" else "cpu",
                max_inference_batch_size=1,
                max_new_tokens=256,
            )

            self.is_loaded = True
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
        audio_data: Union[np.ndarray, str, Path],
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> Optional[TranscriptionResult]:
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

            # Perform transcription with optimized settings
            # Use English as default for better accuracy, or None for auto-detection
            results = self.model.transcribe(
                audio=audio_input,
                language="English",  # Force English for better accuracy - change to None for auto-detect
            )

            # Extract text from result
            if results and len(results) > 0:
                result = results[0]
                text = result.text.strip()
                detected_language = result.language if hasattr(result, "language") else None

                if text:
                    return TranscriptionResult(
                        text=text,
                        timestamp=time.time() * 1000,
                        is_final=True,
                        confidence=None,
                    )

            return None

        except Exception as e:
            logger.error("Transcription error", error=str(e))
            self.error.emit(f"Transcription error: {str(e)}")
            return None

    def _resample_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio to target sample rate."""
        if orig_sr == target_sr:
            return audio

        if (
            TORCHAUDIO_AVAILABLE
            and torchaudio is not None
            and TORCH_AVAILABLE
            and torch is not None
        ):
            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio).unsqueeze(0)

            # Resample
            resampler = torchaudio.transforms.Resample(orig_sr, target_sr)
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
    """Manager for transcription operations."""

    transcription_ready = Signal(TranscriptionResult)
    speaker_updated = Signal(str, str)  # message_id, speaker
    error = Signal(str)

    def __init__(self):
        super().__init__()
        # Get model size from config
        config = get_config()
        model_size = config.get("qwen_asr.model_size", "1.7B")
        self.asr = Qwen3ASR(model_size=model_size)
        self.worker = None
        self.audio_buffer = []

    def initialize(self) -> bool:
        """Initialize the ASR model."""
        self.asr.model_loaded.connect(self._on_model_loaded)
        self.asr.error.connect(self.error.emit)
        # Load model with configured size
        config = get_config()
        model_size = config.get("qwen_asr.model_size", "1.7B")
        return self.asr.load_model(model_size=model_size)

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


class ASRWorker(QThread):
    """Background worker for ASR processing."""

    transcription_ready = Signal(TranscriptionResult)
    error_occurred = Signal(str)

    def __init__(self, asr_model: Qwen3ASR):
        super().__init__()
        self.asr_model = asr_model
        self.audio_queue = []
        self.audio_buffer = []
        self.buffer_duration = 0.0
        self.min_process_duration = 3.0  # Process at least 3 seconds of audio
        self.max_process_duration = 8.0  # Maximum 8 seconds to avoid memory issues
        self.sample_rate = 16000
        self.is_running = False

    def add_audio(self, audio_data: np.ndarray, sample_rate: int = 16000):
        """Add audio data to the processing queue."""
        self.audio_queue.append((audio_data.copy(), sample_rate))

    def run(self):
        """Process audio queue with buffering for better ASR accuracy."""
        self.is_running = True

        while self.is_running:
            # Collect audio from queue
            while self.audio_queue:
                audio_data, sr = self.audio_queue.pop(0)
                self.audio_buffer.append(audio_data)
                self.sample_rate = sr
                self.buffer_duration += len(audio_data) / sr

            # Process audio when we have enough data
            if self.buffer_duration >= self.min_process_duration:
                self._process_buffer()

            self.msleep(50)  # 50ms delay for more responsive processing

    def _process_buffer(self):
        """Process accumulated audio buffer."""
        if not self.audio_buffer:
            return

        # Concatenate all audio in buffer
        audio_data = np.concatenate(self.audio_buffer)

        # Trim to max duration if needed
        max_samples = int(self.max_process_duration * self.sample_rate)
        if len(audio_data) > max_samples:
            audio_data = audio_data[-max_samples:]

        # Transcribe
        result = self.asr_model.transcribe_audio(audio_data, self.sample_rate)

        if result:
            self.transcription_ready.emit(result)

        # Clear buffer after processing
        self.audio_buffer = []
        self.buffer_duration = 0.0

    def stop(self):
        """Stop the worker."""
        self.is_running = False
        self.wait()
