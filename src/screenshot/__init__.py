"""Screenshot capture module for interval-based screen capture."""

from .capture import ScreenshotCapture, ScreenshotCaptureThread
from .storage import ScreenshotStorage

__all__ = ["ScreenshotCapture", "ScreenshotCaptureThread", "ScreenshotStorage"]
