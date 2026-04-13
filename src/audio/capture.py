"""Audio capture module for PipeWire/PulseAudio."""

import subprocess
import threading
import queue
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional, Dict, Any
import numpy as np
import sounddevice as sd
import soundfile as sf
from PySide6.QtCore import QObject, Signal, QThread

from ..utils.logger import get_logger
from ..utils.config import get_config

logger = get_logger(__name__)


class SourceType(Enum):
    """Audio source types."""

    HARDWARE = "hardware"
    MONITOR = "monitor"
    APPLICATION = "application"


@dataclass
class AudioSource:
    """Represents an audio source."""

    name: str
    description: str
    index: int
    source_type: SourceType
    is_monitor: bool = False
    process_id: Optional[int] = None
    sink_input_id: Optional[int] = None
    icon_name: Optional[str] = None


@dataclass
class AudioProcess:
    """Represents an audio-producing process."""

    name: str
    pid: int
    sink_input_id: int
    icon_name: Optional[str] = None


class AudioCaptureThread(QThread):
    """Thread for capturing audio without blocking GUI."""

    data_ready = Signal(np.ndarray)
    error_occurred = Signal(str)

    def __init__(self, source_name: str, sample_rate: int = 16000, channels: int = 1):
        super().__init__()
        self.source_name = source_name
        self.sample_rate = sample_rate
        self.channels = channels
        self._running = False
        self._process: Optional[subprocess.Popen] = None
        self._loopback_modules: List[int] = []

    def run(self):
        """Main capture loop."""
        self._running = True
        logger.info("Starting audio capture", source=self.source_name)

        try:
            # Use parec for PulseAudio capture
            cmd = [
                "parec",
                "-d",
                self.source_name,
                "--format",
                "s16le",
                "--rate",
                str(self.sample_rate),
                "--channels",
                str(self.channels),
            ]

            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=4096
            )

            # Read audio data in chunks - use 2 second chunks for better ASR accuracy
            chunk_size = int(self.sample_rate * 2.0 * self.channels * 2)  # 2 second chunks

            while self._running and self._process.poll() is None:
                data = self._process.stdout.read(chunk_size)
                if not data:
                    break

                # Convert to numpy array
                audio_array = np.frombuffer(data, dtype=np.int16)
                self.data_ready.emit(audio_array)

        except Exception as e:
            logger.error("Audio capture error", error=str(e))
            self.error_occurred.emit(str(e))
        finally:
            self.stop()

    def stop(self):
        """Stop audio capture."""
        self._running = False
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

        # Cleanup loopback modules
        for module_id in self._loopback_modules:
            try:
                subprocess.run(
                    ["pactl", "unload-module", str(module_id)], capture_output=True, check=False
                )
            except Exception as e:
                logger.warning("Failed to unload module", module_id=module_id, error=str(e))

        self._loopback_modules = []
        logger.info("Audio capture stopped")


class AudioCapture(QObject):
    """Manages audio capture from PipeWire/PulseAudio sources."""

    # Signals
    audio_data = Signal(np.ndarray)
    error = Signal(str)
    source_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._capture_thread: Optional[AudioCaptureThread] = None
        self._current_source: Optional[str] = None
        self._is_recording = False
        self._audio_buffer: queue.Queue = queue.Queue(maxsize=100)
        self._loopback_modules: List[int] = []

    def list_sources(self) -> List[AudioSource]:
        """List available audio sources."""
        sources = []

        try:
            result = subprocess.run(
                ["pactl", "list", "sources"], capture_output=True, text=True, check=True
            )

            # Parse pactl output
            current_source = None
            current_block = ""

            for line in result.stdout.split("\n"):
                if line.startswith("Source #"):
                    # Parse previous block if exists
                    if current_source is not None and current_block:
                        source = self._parse_source_block(current_source, current_block)
                        if source:
                            sources.append(source)

                    # Start new block
                    current_source = int(line.split("#")[1].strip())
                    current_block = line + "\n"
                elif current_source is not None:
                    current_block += line + "\n"

            # Parse last block
            if current_source is not None and current_block:
                source = self._parse_source_block(current_source, current_block)
                if source:
                    sources.append(source)

        except subprocess.CalledProcessError as e:
            logger.error("Failed to list sources", error=str(e))
        except FileNotFoundError:
            logger.error("pactl not found. Is PulseAudio/PipeWire installed?")

        return sources

    def _parse_source_block(self, index: int, block: str) -> Optional[AudioSource]:
        """Parse a pactl source block."""
        name = None
        description = ""
        is_monitor = False

        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("Name: "):
                name = line.split(": ", 1)[1]
                is_monitor = ".monitor" in name
            elif line.startswith("Description: "):
                description = line.split(": ", 1)[1]

        if name:
            source_type = SourceType.MONITOR if is_monitor else SourceType.HARDWARE
            return AudioSource(
                name=name,
                description=description or name,
                index=index,
                source_type=source_type,
                is_monitor=is_monitor,
            )
        return None

    def list_audio_processes(self) -> List[AudioProcess]:
        """List processes producing audio."""
        processes = []

        try:
            result = subprocess.run(
                ["pactl", "list", "sink-inputs"], capture_output=True, text=True, check=True
            )

            current_sink_input = None
            current_block = ""

            for line in result.stdout.split("\n"):
                if line.startswith("Sink Input #"):
                    if current_sink_input is not None and current_block:
                        process = self._parse_sink_input_block(current_sink_input, current_block)
                        if process:
                            processes.append(process)

                    current_sink_input = int(line.split("#")[1].strip())
                    current_block = line + "\n"
                elif current_sink_input is not None:
                    current_block += line + "\n"

            # Parse last block
            if current_sink_input is not None and current_block:
                process = self._parse_sink_input_block(current_sink_input, current_block)
                if process:
                    processes.append(process)

        except subprocess.CalledProcessError as e:
            logger.error("Failed to list sink inputs", error=str(e))
        except FileNotFoundError:
            logger.error("pactl not found")

        return processes

    def _parse_sink_input_block(self, sink_input_id: int, block: str) -> Optional[AudioProcess]:
        """Parse a pactl sink input block."""
        name = None
        pid = None
        icon_name = None

        for line in block.split("\n"):
            line = line.strip()
            if 'application.name = "' in line:
                name = line.split('"')[1]
            elif 'application.process.id = "' in line:
                pid = int(line.split('"')[1])
            elif 'application.icon_name = "' in line:
                icon_name = line.split('"')[1]

        if name and pid:
            return AudioProcess(
                name=name, pid=pid, sink_input_id=sink_input_id, icon_name=icon_name
            )
        return None

    def list_all_sources(self) -> List[AudioSource]:
        """List all audio sources including hardware, monitors, and applications."""
        sources = self.list_sources()

        # Add application sources
        try:
            processes = self.list_audio_processes()
            for process in processes:
                app_source = AudioSource(
                    name=f"app-pid-{process.pid}",
                    description=f"{process.name} (PID: {process.pid})",
                    index=process.sink_input_id,
                    source_type=SourceType.APPLICATION,
                    is_monitor=False,
                    process_id=process.pid,
                    sink_input_id=process.sink_input_id,
                    icon_name=process.icon_name,
                )
                sources.append(app_source)
        except Exception as e:
            logger.error("Failed to list application sources", error=str(e))

        return sources

    def start_capture(
        self, source_name: str, source_type: SourceType = SourceType.HARDWARE
    ) -> bool:
        """Start capturing audio from a source."""
        if self._is_recording:
            logger.warning("Already recording, stop first")
            return False

        config = get_config()
        sample_rate = config.get("audio.sample_rate", 16000)

        # Handle application sources
        actual_source = source_name
        if source_type == SourceType.APPLICATION:
            # Extract PID and create loopback
            import re

            match = re.match(r"app-pid-(\d+)", source_name)
            if match:
                pid = int(match.group(1))
                actual_source = self._create_application_loopback(pid)
                if not actual_source:
                    self.error.emit("Failed to create application loopback")
                    return False

        # Start capture thread
        self._capture_thread = AudioCaptureThread(actual_source, sample_rate)
        self._capture_thread.data_ready.connect(self._on_audio_data)
        self._capture_thread.error_occurred.connect(self.error)
        self._capture_thread.start()

        self._current_source = source_name
        self._is_recording = True
        self.source_changed.emit(source_name)

        logger.info("Audio capture started", source=source_name)
        return True

    def _create_application_loopback(self, pid: int) -> Optional[str]:
        """Create a loopback module for capturing application audio."""
        try:
            # Find the sink input for this PID
            processes = self.list_audio_processes()
            process = next((p for p in processes if p.pid == pid), None)

            if not process:
                logger.error("No audio process found for PID", pid=pid)
                return None

            # Create null sink
            sink_name = f"app_capture_{pid}"
            result = subprocess.run(
                [
                    "pactl",
                    "load-module",
                    "module-null-sink",
                    f"sink_name={sink_name}",
                    f"sink_properties=device.description=App_Audio_Capture_{pid}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            sink_module_id = int(result.stdout.strip())
            self._loopback_modules.append(sink_module_id)

            # Move sink input to null sink
            subprocess.run(
                ["pactl", "move-sink-input", str(process.sink_input_id), sink_name],
                capture_output=True,
                check=False,  # Continue even if this fails
            )

            # Create loopback to route audio back to default sink
            result = subprocess.run(
                [
                    "pactl",
                    "load-module",
                    "module-loopback",
                    f"source={sink_name}.monitor",
                    "sink=@DEFAULT_SINK@",
                    "latency_msec=1",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            loopback_module_id = int(result.stdout.strip())
            self._loopback_modules.append(loopback_module_id)

            # Wait for modules to initialize
            import time

            time.sleep(0.25)

            monitor_source = f"{sink_name}.monitor"
            logger.info(
                "Created application loopback",
                source=monitor_source,
                modules=self._loopback_modules,
            )
            return monitor_source

        except Exception as e:
            logger.error("Failed to create application loopback", error=str(e))
            return None

    def _on_audio_data(self, data: np.ndarray):
        """Handle incoming audio data."""
        self.audio_data.emit(data)

    def stop_capture(self):
        """Stop audio capture."""
        if self._capture_thread:
            self._capture_thread.stop()
            self._capture_thread.wait(3000)  # Wait up to 3 seconds
            self._capture_thread = None

        self._is_recording = False
        self._current_source = None
        self.source_changed.emit("")

        logger.info("Audio capture stopped")

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    def get_current_source(self) -> Optional[str]:
        """Get current audio source name."""
        return self._current_source
