"""E2E tests for Audio Recorder application."""

import os
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest


# Set up paths before importing application modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def clean_config(tmp_path, monkeypatch):
    """Create a clean config directory for testing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.setattr("src.utils.config.user_config_dir", lambda x: str(config_dir))
    # Clear any cached config
    from src.utils import config as config_module

    config_module._config_instance = None
    yield
    config_module._config_instance = None


@pytest.fixture
def mock_qtimer():
    """Mock QTimer to avoid Qt event loop issues in tests."""
    with patch("PySide6.QtCore.QTimer") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock


class TestConfigDataclass:
    """Test that config dataclasses work correctly."""

    def test_priority_queue_config_attributes(self, clean_config):
        """Test PriorityQueueConfig dataclass has correct attributes."""
        from src.utils.config import get_config, PriorityQueueConfig

        config = get_config()
        pq = config.get("priority_queue", None)

        assert pq is not None
        assert hasattr(pq, "enabled")
        assert hasattr(pq, "aging_interval")
        assert hasattr(pq, "aging_factor")
        assert hasattr(pq, "max_age")
        assert hasattr(pq, "max_concurrent")

    def test_local_llm_config_attributes(self, clean_config):
        """Test LocalLLMConfig dataclass has correct attributes."""
        from src.utils.config import get_config, LocalLLMConfig

        config = get_config()
        llm = config.get("local_llm", None)

        assert llm is not None
        assert hasattr(llm, "enabled")
        assert hasattr(llm, "base_url")
        assert hasattr(llm, "model_name")
        assert hasattr(llm, "api_key")
        assert hasattr(llm, "timeout")

    def test_screenshot_config_attributes(self, clean_config):
        """Test ScreenshotConfig dataclass has correct attributes."""
        from src.utils.config import get_config, ScreenshotConfig

        config = get_config()
        sc = config.get("screenshot", None)

        assert sc is not None
        assert hasattr(sc, "enabled")
        assert hasattr(sc, "interval")
        assert hasattr(sc, "max_count")


class TestPriorityQueueManager:
    """Test PriorityQueueManager initialization and lifecycle."""

    def test_priority_queue_init_no_event_loop(self, clean_config, mock_qtimer):
        """Test PriorityQueueManager can be instantiated without an event loop."""
        from src.ai.priority_queue import PriorityQueueManager

        pq = PriorityQueueManager()
        assert pq is not None
        assert pq.enabled in [True, False]

    def test_priority_queue_start_stop(self, clean_config, mock_qtimer):
        """Test PriorityQueueManager start and stop."""
        from src.ai.priority_queue import PriorityQueueManager

        pq = PriorityQueueManager()
        pq.start()
        assert pq._running is True
        assert pq._asyncio_loop is not None
        assert pq._asyncio_thread is not None

        pq.stop()
        assert pq._running is False


class TestScreenshotStorage:
    """Test ScreenshotStorage functionality."""

    def test_storage_init(self, clean_config, tmp_path):
        """Test ScreenshotStorage initialization."""
        from src.screenshot.storage import ScreenshotStorage

        storage_dir = tmp_path / "screenshots"
        storage = ScreenshotStorage(max_count=10, storage_dir=str(storage_dir))

        assert storage._max_count == 10
        assert str(storage._storage_dir) == str(storage_dir)
        assert storage.get_buffer_count() == 0

    def test_storage_add_and_evict(self, clean_config, tmp_path):
        """Test adding screenshots and circular buffer eviction."""
        from src.screenshot.storage import ScreenshotStorage
        from PIL import Image

        storage_dir = tmp_path / "screenshots"
        storage = ScreenshotStorage(max_count=3, storage_dir=str(storage_dir))

        # Create mock PIL images and add them
        for i in range(3):
            img = Image.new("RGB", (100, 100), color="red")
            storage.add(img)

        assert storage.get_buffer_count() == 3

        # Add 4th screenshot - should evict oldest
        img = Image.new("RGB", (100, 100), color="blue")
        storage.add(img)

        assert storage.get_buffer_count() == 3

    def test_get_recent(self, clean_config, tmp_path):
        """Test getting recent screenshots."""
        from src.screenshot.storage import ScreenshotStorage
        from PIL import Image

        storage_dir = tmp_path / "screenshots"
        storage = ScreenshotStorage(max_count=10, storage_dir=str(storage_dir))

        for i in range(5):
            img = Image.new("RGB", (100, 100), color="green")
            storage.add(img)

        recent = storage.get_recent(3)
        assert len(recent) == 3


class TestDatabaseManager:
    """Test DatabaseManager functionality."""

    def test_database_init(self, clean_config, tmp_path):
        """Test DatabaseManager initialization."""
        from src.database.manager import DatabaseManager
        from pathlib import Path

        db_path = tmp_path / "test.db"
        # Pass as Path object, not string
        db = DatabaseManager(db_path=db_path)

        assert db is not None
        # Initialize the database
        result = db.initialize()
        assert result is True
        assert db.engine is not None


class TestConfigManager:
    """Test ConfigManager get/set methods."""

    def test_get_nested_attribute(self, clean_config):
        """Test getting nested config attributes."""
        from src.utils.config import get_config

        config = get_config()

        # Test priority_queue config
        pq = config.get("priority_queue", None)
        assert pq is not None

        # Test stt config
        stt = config.get("stt", None)
        assert stt is not None

    def test_set_nested_attribute(self, clean_config):
        """Test setting nested config attributes."""
        from src.utils.config import get_config

        config = get_config()

        # Set and get a value
        config.set("priority_queue.enabled", False)
        pq = config.get("priority_queue")
        assert pq.enabled is False

    def test_get_with_default(self, clean_config):
        """Test getting config with default value."""
        from src.utils.config import get_config

        config = get_config()

        # Get existing value
        val = config.get("stt.language", "auto")
        assert val in ["auto", "en", "ru", "uk"]

        # Get non-existent with default
        val = config.get("nonexistent.key", "default_value")
        assert val == "default_value"


class TestScreenshotAnalyzer:
    """Test ScreenshotAnalyzer functionality."""

    def test_analyzer_init(self, clean_config):
        """Test ScreenshotAnalyzer initialization."""
        from src.screenshot.analyzer import ScreenshotAnalyzer
        from src.ai.openrouter import AISuggestionGenerator

        mock_generator = Mock(spec=AISuggestionGenerator)
        analyzer = ScreenshotAnalyzer(ai_generator=mock_generator)

        assert analyzer is not None
        assert analyzer._ai_generator is mock_generator


class TestImportChain:
    """Test that all main modules can be imported."""

    def test_import_utils(self):
        """Test utils module imports."""
        from src.utils import logger, config

        assert logger is not None
        assert config is not None

    def test_import_ai(self):
        """Test AI module imports."""
        from src.ai import priority_queue, openrouter

        assert priority_queue is not None
        assert openrouter is not None

    def test_import_speech(self):
        """Test speech module imports."""
        from src.speech import asr, diarization

        assert asr is not None
        assert diarization is not None

    def test_import_screenshot(self):
        """Test screenshot module imports."""
        from src.screenshot import capture, storage, analyzer

        assert capture is not None
        assert storage is not None
        assert analyzer is not None

    def test_import_database(self):
        """Test database module imports."""
        from src.database import manager

        assert manager is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
