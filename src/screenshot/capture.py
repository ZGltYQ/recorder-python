"""Screenshot capture using QThread for non-blocking capture."""

import os
from pathlib import Path
from typing import Optional
from collections import deque

from PySide6.QtCore import QObject, Signal, QThread, QTimer

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Try to import mss for screen capture, fall back to Qt screen capture
try:
    import mss
    import mss.tools

    HAS_MSS = True
except ImportError:
    HAS_MSS = False
    logger.warning("mss not available, will use Qt screen capture")


class ScreenshotCaptureThread(QThread):
    """Thread for capturing screenshots at configured intervals without blocking GUI."""

    screenshot_ready = Signal(object)  # Emits PIL Image or None
    error_occurred = Signal(str)

    def __init__(self, interval: int = 30, parent: Optional[QObject] = None):
        """Initialize screenshot capture thread.

        Args:
            interval: Capture interval in seconds (5-300)
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._interval = max(5, min(300, interval))  # Clamp to valid range
        self._running = False
        self._timer: Optional[QTimer] = None
        self._screenshot_count = 0

        if HAS_MSS:
            self._mss_instance = mss.mss()
        else:
            self._mss_instance = None

    def run(self):
        """Main capture loop running in thread."""
        self._running = True
        logger.info("Starting screenshot capture", interval=self._interval)

        # Create and start timer in the thread
        self._timer = QTimer()
        self._timer.moveToThread(self)
        self._timer.timeout.connect(self._capture)
        # Use slotConnectionType for queued connection to run in thread
        self._timer.setSingleShot(False)
        self._timer.start(self._interval * 1000)  # Convert to milliseconds

        # Run event loop for this thread
        self.exec()

    def _capture(self):
        """Perform a single screenshot capture."""
        if not self._running:
            return

        try:
            if self._mss_instance is not None:
                # Use mss for capture
                screenshot = self._mss_instance.grab(self._mss_instance.monitors[1])
                # Convert to PNG data for storage
                import mss.tools
                from PIL import Image
                import numpy as np

                # mss returns BGRA, convert to RGB
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            else:
                # Use Qt screen capture as fallback
                from PySide6.QtWidgets import QApplication
                from PySide6.QtGui import QScreen

                app = QApplication.instance()
                if app is None:
                    logger.error("No QApplication instance found")
                    return

                screen: QScreen = app.primaryScreen()
                if screen is None:
                    logger.error("No primary screen found")
                    return

                # Capture the entire screen
                pixmap = screen.grabWindow(0)
                from PIL import Image

                img = Image.fromqpixmap(pixmap)

            self._screenshot_count += 1
            logger.debug("Screenshot captured", count=self._screenshot_count)
            self.screenshot_ready.emit(img)

        except Exception as e:
            logger.error("Screenshot capture failed", error=str(e))
            self.error_occurred.emit(str(e))

    def stop(self):
        """Stop screenshot capture."""
        logger.info("Stopping screenshot capture", captures=self._screenshot_count)
        self._running = False

        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None

        if self._mss_instance is not None:
            self._mss_instance.close()
            self._mss_instance = None

        # Quit the event loop
        self.quit()
        self.wait(3000)  # Wait up to 3 seconds
        logger.info("Screenshot capture stopped")

    def update_interval(self, interval: int):
        """Update the capture interval.

        Args:
            interval: New interval in seconds
        """
        self._interval = max(5, min(300, interval))
        if self._timer is not None and self._running:
            self._timer.setInterval(self._interval * 1000)
            logger.info("Screenshot interval updated", interval=self._interval)


class ScreenshotCapture(QObject):
    """Manages screenshot capture from screen.

    Provides a high-level interface for starting/stopping screenshot capture
    and forwards signals from the capture thread.
    """

    screenshot_ready = Signal(object)  # Emits PIL Image
    capture_enabled = Signal(bool)  # Toggle state changed
    error = Signal(str)

    def __init__(self, parent: Optional[QObject] = None):
        """Initialize screenshot capture manager.

        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._capture_thread: Optional[ScreenshotCaptureThread] = None
        self._is_enabled = False
        self._current_interval = 30

    def start(self, interval: int = 30) -> bool:
        """Start screenshot capture.

        Args:
            interval: Capture interval in seconds (default 30)

        Returns:
            True if capture started successfully
        """
        if self._is_enabled:
            logger.warning("Screenshot capture already enabled")
            return True

        try:
            self._current_interval = interval
            self._capture_thread = ScreenshotCaptureThread(interval)
            self._capture_thread.screenshot_ready.connect(self._on_screenshot_ready)
            self._capture_thread.error_occurred.connect(self.error)
            self._capture_thread.start()

            self._is_enabled = True
            self.capture_enabled.emit(True)
            logger.info("Screenshot capture started", interval=interval)
            return True

        except Exception as e:
            logger.error("Failed to start screenshot capture", error=str(e))
            self.error.emit(str(e))
            return False

    def stop(self):
        """Stop screenshot capture."""
        if not self._is_enabled:
            return

        if self._capture_thread is not None:
            self._capture_thread.stop()
            self._capture_thread = None

        self._is_enabled = False
        self.capture_enabled.emit(False)
        logger.info("Screenshot capture stopped")

    def is_enabled(self) -> bool:
        """Check if screenshot capture is enabled.

        Returns:
            True if capture is running
        """
        return self._is_enabled

    def update_interval(self, interval: int):
        """Update the capture interval.

        Args:
            interval: New interval in seconds
        """
        self._current_interval = interval
        if self._capture_thread is not None and self._is_enabled:
            self._capture_thread.update_interval(interval)

    def _on_screenshot_ready(self, image):
        """Handle screenshot from capture thread.

        Args:
            image: PIL Image from capture
        """
        self.screenshot_ready.emit(image)
