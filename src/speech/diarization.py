"""Speaker diarization module using Resemblyzer."""

import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np
from PySide6.QtCore import QObject, Signal, QThread

from ..utils.logger import get_logger
from ..utils.config import get_config

logger = get_logger(__name__)

# Try to import Resemblyzer
try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    from sklearn.cluster import AgglomerativeClustering

    RESEMBLYZER_AVAILABLE = True
except ImportError:
    RESEMBLYZER_AVAILABLE = False
    logger.warning("Resemblyzer not available. Speaker diarization disabled.")


@dataclass
class SpeakerUpdate:
    """Represents a speaker assignment update."""

    message_id: str
    speaker: str


@dataclass
class DiarizationChunk:
    """Represents an audio chunk for diarization."""

    chunk_id: int
    audio_data: np.ndarray
    message_ids: List[str]
    timestamps: List[Tuple[float, float]]  # (start, end) for each message


class DiarizationProcessor(QThread):
    """Background thread for speaker diarization."""

    speaker_ready = Signal(list)  # List[SpeakerUpdate]
    error_occurred = Signal(str)

    def __init__(self, sample_rate: int = 16000):
        super().__init__()
        self.sample_rate = sample_rate
        self._running = False
        self._queue: Queue[DiarizationChunk] = Queue()
        self._encoder = None
        self._speaker_embeddings: Dict[int, int] = {}
        self._speaker_counter = 0

        if RESEMBLYZER_AVAILABLE:
            try:
                logger.info("Loading Resemblyzer voice encoder...")
                self._encoder = VoiceEncoder()
                logger.info("Resemblyzer loaded successfully")
            except Exception as e:
                logger.error("Failed to load Resemblyzer", error=str(e))

    def add_chunk(
        self,
        chunk_id: int,
        audio_data: np.ndarray,
        message_ids: List[str],
        timestamps: List[Tuple[float, float]],
    ):
        """Add audio chunk for diarization."""
        chunk = DiarizationChunk(
            chunk_id=chunk_id, audio_data=audio_data, message_ids=message_ids, timestamps=timestamps
        )
        self._queue.put(chunk)
        logger.debug("Added chunk for diarization", chunk_id=chunk_id, messages=len(message_ids))

    def run(self):
        """Main diarization loop."""
        self._running = True

        while self._running:
            try:
                # Get chunk from queue (blocking with timeout)
                import time

                try:
                    chunk = self._queue.get(timeout=1.0)
                except:
                    continue

                if not self._encoder:
                    logger.warning("Encoder not available, skipping diarization")
                    continue

                # Process chunk
                self._process_chunk(chunk)

            except Exception as e:
                logger.error("Diarization error", error=str(e))
                self.error_occurred.emit(str(e))

    def _process_chunk(self, chunk: DiarizationChunk):
        """Process a single diarization chunk."""
        try:
            logger.info("Processing diarization chunk", chunk_id=chunk.chunk_id)

            # Save audio to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name

                with wave.open(tmp_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(chunk.audio_data.tobytes())

            # Preprocess audio
            try:
                wav = preprocess_wav(tmp_path)
            except Exception as e:
                logger.error("Failed to preprocess audio", error=str(e))
                Path(tmp_path).unlink(missing_ok=True)
                return
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            # Check audio quality
            if np.isnan(wav).any() or np.isinf(wav).any():
                logger.warning("Invalid audio data (NaN/Inf), skipping")
                return

            rms = np.sqrt(np.mean(wav**2))
            if rms < 0.001:
                logger.warning("Audio too quiet, skipping", rms=rms)
                return

            # Extract embeddings for each message
            embeddings = []
            valid_message_ids = []

            chunk_start_time = chunk.chunk_id * 10  # Each chunk is 10 seconds

            for i, (msg_id, (start, end)) in enumerate(zip(chunk.message_ids, chunk.timestamps)):
                # Calculate sample indices
                start_sample = int((start - chunk_start_time) * self.sample_rate)
                end_sample = int((end - chunk_start_time) * self.sample_rate)

                # Clamp to valid range
                start_sample = max(0, min(start_sample, len(wav)))
                end_sample = max(start_sample, min(end_sample, len(wav)))

                if end_sample - start_sample < self.sample_rate * 0.3:  # At least 0.3 seconds
                    continue

                segment = wav[start_sample:end_sample]

                # Check segment quality
                if np.isnan(segment).any() or np.isinf(segment).any():
                    continue

                seg_rms = np.sqrt(np.mean(segment**2))
                if seg_rms < 0.01:
                    continue

                try:
                    # Extract embedding
                    embed = self._encoder.embed_utterance(segment)

                    if not (np.isnan(embed).any() or np.isinf(embed).any()):
                        embeddings.append(embed)
                        valid_message_ids.append(msg_id)
                except Exception as e:
                    logger.warning("Failed to extract embedding", message_id=msg_id, error=str(e))

            if not embeddings:
                logger.warning("No valid embeddings extracted")
                return

            embeddings = np.array(embeddings)

            # Cluster embeddings
            n_speakers = min(len(embeddings), 6)

            if len(embeddings) > 1:
                clustering = AgglomerativeClustering(
                    n_clusters=None, distance_threshold=0.5, linkage="average"
                )
                labels = clustering.fit_predict(embeddings)
            else:
                labels = np.array([0])

            # Create speaker updates
            updates = []
            for msg_id, cluster_id in zip(valid_message_ids, labels):
                if cluster_id not in self._speaker_embeddings:
                    self._speaker_embeddings[cluster_id] = self._speaker_counter
                    self._speaker_counter += 1

                speaker_name = f"Speaker_{self._speaker_embeddings[cluster_id]}"
                updates.append(SpeakerUpdate(message_id=msg_id, speaker=speaker_name))

            if updates:
                logger.info(
                    "Speaker identification complete",
                    chunk_id=chunk.chunk_id,
                    speakers=len(updates),
                )
                self.speaker_ready.emit(updates)

        except Exception as e:
            logger.error("Error processing chunk", chunk_id=chunk.chunk_id, error=str(e))
            self.error_occurred.emit(str(e))

    def stop(self):
        """Stop the diarization processor."""
        self._running = False
        self.wait(2000)

    def is_available(self) -> bool:
        """Check if diarization is available."""
        return RESEMBLYZER_AVAILABLE and self._encoder is not None


class SpeakerDiarization(QObject):
    """Manages speaker diarization."""

    speaker_updated = Signal(str, str)  # message_id, speaker
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.processor: Optional[DiarizationProcessor] = None
        self._audio_chunks: List[np.ndarray] = []
        self._chunk_counter = 0
        self._message_tracker: List[Dict] = []
        self._sample_rate = 16000

    def initialize(self) -> bool:
        """Initialize speaker diarization."""
        config = get_config()

        if not config.get("diarization.enabled", True):
            logger.info("Speaker diarization disabled in config")
            return False

        if not RESEMBLYZER_AVAILABLE:
            logger.warning("Resemblyzer not available, diarization disabled")
            return False

        self.processor = DiarizationProcessor(self._sample_rate)
        self.processor.speaker_ready.connect(self._on_speakers_ready)
        self.processor.error_occurred.connect(self.error)
        self.processor.start()

        logger.info("Speaker diarization initialized")
        return True

    def start(self):
        """Start diarization."""
        self._audio_chunks = []
        self._chunk_counter = 0
        self._message_tracker = []
        logger.info("Speaker diarization started")

    def stop(self):
        """Stop diarization."""
        if self.processor:
            self.processor.stop()
        logger.info("Speaker diarization stopped")

    def add_audio(self, audio_data: np.ndarray):
        """Add audio data for diarization."""
        if not self.processor or not self.processor.is_available():
            return

        self._audio_chunks.append(audio_data)

        # Process every 10 seconds of audio
        chunk_samples = self._sample_rate * 10
        total_samples = sum(len(chunk) for chunk in self._audio_chunks)

        if total_samples >= chunk_samples:
            # Concatenate chunks
            audio_buffer = np.concatenate(self._audio_chunks)

            # Take exactly 10 seconds
            process_data = audio_buffer[:chunk_samples]
            remaining = audio_buffer[chunk_samples:]

            # Get messages for this chunk
            chunk_messages = [
                m for m in self._message_tracker if m.get("chunk_id") == self._chunk_counter
            ]

            if chunk_messages:
                message_ids = [m["id"] for m in chunk_messages]
                timestamps = [(m["start"], m["end"]) for m in chunk_messages]

                self.processor.add_chunk(self._chunk_counter, process_data, message_ids, timestamps)

            self._chunk_counter += 1
            self._audio_chunks = [remaining] if len(remaining) > 0 else []

    def track_message(self, message_id: str, start_time: float, end_time: float, text: str):
        """Track a message for speaker assignment."""
        chunk_id = int(start_time / 10)

        self._message_tracker.append(
            {
                "id": message_id,
                "start": start_time,
                "end": end_time,
                "text": text,
                "chunk_id": chunk_id,
            }
        )

        logger.debug("Tracking message", message_id=message_id, chunk_id=chunk_id, text=text[:50])

    def _on_speakers_ready(self, updates: List[SpeakerUpdate]):
        """Handle speaker identification results."""
        for update in updates:
            self.speaker_updated.emit(update.message_id, update.speaker)

    def is_available(self) -> bool:
        """Check if diarization is available."""
        return self.processor is not None and self.processor.is_available()
