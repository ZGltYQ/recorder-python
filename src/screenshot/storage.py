"""Screenshot storage with circular buffer retention policy."""

import json
import os
from pathlib import Path
from collections import deque
from datetime import datetime
from typing import List, Optional

from appdirs import user_config_dir

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ScreenshotStorage:
    """Manages screenshot storage with circular buffer retention policy.

    Screenshots are stored in a configurable directory and managed with
    a deque-based circular buffer that automatically evicts the oldest
    screenshots when the configured max_count is exceeded.
    """

    def __init__(self, max_count: int = 50, storage_dir: Optional[str] = None):
        """Initialize screenshot storage.

        Args:
            max_count: Maximum number of screenshots to retain (circular buffer size)
            storage_dir: Directory to store screenshots. Defaults to
                        ~/.config/recorder-python/screenshots/
        """
        self._max_count = max(1, max_count)  # Ensure at least 1
        self._storage_dir = Path(
            storage_dir if storage_dir else Path(user_config_dir("recorder-python")) / "screenshots"
        )
        self._buffer: deque = deque(maxlen=self._max_count)

        # Ensure storage directory exists
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        # Load existing screenshots from disk into buffer
        self._load_existing()

        logger.info(
            "ScreenshotStorage initialized",
            max_count=self._max_count,
            storage_dir=str(self._storage_dir),
            current_count=self.get_buffer_count(),
        )

    def _load_existing(self):
        """Load existing screenshots from disk into buffer."""
        try:
            if not self._storage_dir.exists():
                return

            # Find all PNG files sorted by modification time
            screenshot_files = sorted(
                self._storage_dir.glob("screenshot_*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,  # Most recent first
            )

            # Add to buffer (deque with maxlen will handle overflow)
            for file_path in screenshot_files[: self._max_count]:
                self._buffer.append(str(file_path))

        except Exception as e:
            logger.error("Failed to load existing screenshots", error=str(e))

    def add(self, image) -> Optional[str]:
        """Add a screenshot to storage.

        Args:
            image: PIL Image to save

        Returns:
            Path to saved screenshot, or None if save failed
        """
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"screenshot_{timestamp}.png"
            filepath = self._storage_dir / filename

            # Save image
            image.save(str(filepath), "PNG")
            image_path = str(filepath)

            # Add to buffer (automatic eviction if full)
            self._buffer.append(image_path)

            logger.debug(
                "Screenshot saved",
                path=image_path,
                buffer_count=self.get_buffer_count(),
            )

            return image_path

        except Exception as e:
            logger.error("Failed to save screenshot", error=str(e))
            return None

    def get_recent(self, count: int = 10) -> List[str]:
        """Get paths to recent screenshots.

        Args:
            count: Number of recent screenshots to return

        Returns:
            List of screenshot file paths, most recent first
        """
        # Return from buffer in reverse order (most recent first)
        recent = list(reversed(self._buffer))
        return recent[: min(count, len(recent))]

    def cleanup(self) -> int:
        """Remove oldest screenshots beyond max_count.

        This is called automatically when adding new screenshots
        (via circular buffer), but can be called manually to enforce
        retention policy.

        Returns:
            Number of screenshots removed
        """
        removed = 0
        while len(self._buffer) > self._max_count:
            oldest_path = self._buffer.popleft()
            try:
                Path(oldest_path).unlink(missing_ok=True)
                removed += 1
                logger.debug("Removed old screenshot", path=oldest_path)
            except Exception as e:
                logger.error("Failed to remove old screenshot", path=oldest_path, error=str(e))

        if removed > 0:
            logger.info("Screenshot cleanup completed", removed=removed)

        return removed

    def get_buffer_count(self) -> int:
        """Get current number of screenshots in buffer.

        Returns:
            Current buffer size
        """
        return len(self._buffer)

    def get_max_count(self) -> int:
        """Get configured maximum screenshot count.

        Returns:
            Maximum buffer size
        """
        return self._max_count

    def get_storage_dir(self) -> str:
        """Get the storage directory path.

        Returns:
            Path to screenshot storage directory
        """
        return str(self._storage_dir)

    def clear(self):
        """Clear all stored screenshots."""
        for path in list(self._buffer):
            try:
                Path(path).unlink(missing_ok=True)
            except Exception as e:
                logger.error("Failed to delete screenshot", path=path, error=str(e))

        self._buffer.clear()
        logger.info("All screenshots cleared")
