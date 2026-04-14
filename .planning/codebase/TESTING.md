# Testing Patterns

**Analysis Date:** 2026-04-14

## Test Framework

**Runner:** pytest (>=7.4.0) - Declared in requirements.txt

**Assertion Library:** pytest built-in

**Run Commands:**
```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest --cov=src          # With coverage
pytest tests/             # Specific directory
```

## Test File Organization

**Location:** `tests/` directory (empty at time of analysis)

**Naming Convention:** Not established (no test files present)

**Recommended Pattern (per pytest conventions):**
```
tests/
├── conftest.py           # Shared fixtures
├── test_module_name.py   # One test file per module
└── ...
```

## Test Structure

**Expected Pattern (based on pytest best practices):**
```python
import pytest
from src.audio.capture import AudioCapture

class TestAudioCapture:
    """Tests for AudioCapture class."""

    def test_list_sources_returns_list(self):
        """Test that list_sources returns a list."""
        capture = AudioCapture()
        sources = capture.list_sources()
        assert isinstance(sources, list)

    def test_list_sources_contains_audio_source(self):
        """Test that sources are AudioSource dataclasses."""
        capture = AudioCapture()
        sources = capture.list_sources()
        if sources:
            assert hasattr(sources[0], 'name')
            assert hasattr(sources[0], 'description')
```

## Mocking

**Framework:** pytest-mock (if installed) or unittest.mock

**Pattern:**
```python
from unittest.mock import Mock, patch, MagicMock

def test_capture_with_mocked_subprocess():
    """Test audio capture with mocked subprocess."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(stdout="Source #1\nName: test")
        capture = AudioCapture()
        sources = capture.list_sources()
        assert len(sources) > 0
```

**Qt Mocking:**
```python
from unittest.mock import Mock, patch

def test_signal_emission():
    """Test Qt signal emission."""
    with patch('PySide6.QtCore.QObject'):
        # Test signal connections
```

## Fixtures and Factories

**Shared Fixtures (conftest.py):**
```python
import pytest
from src.utils.config import ConfigManager, AppConfig

@pytest.fixture
def config_manager():
    """Provide a test config manager."""
    return ConfigManager(app_name="test-recorder")

@pytest.fixture
def sample_audio_data():
    """Provide sample numpy audio data."""
    import numpy as np
    return np.random.randn(16000).astype(np.int16)
```

**Test Data Factories:**
```python
def create_audio_source(name="Test Source", description="Test"):
    """Factory for AudioSource dataclass."""
    from src.audio.capture import AudioSource, SourceType
    return AudioSource(
        name=name,
        description=description,
        index=0,
        source_type=SourceType.HARDWARE,
    )
```

## Coverage

**No coverage target enforced** - Not detected in configuration

**View Coverage:**
```bash
pytest --cov=src --cov-report=html
```

## Test Types

**Unit Tests:**
- Focus on individual class/method testing
- Mock external dependencies (subprocess, audio devices)
- Example files: `tests/test_audio_capture.py`, `tests/test_database.py`

**Integration Tests:**
- Test interactions between modules
- Example: `tests/test_transcription_flow.py`

**E2E Tests:**
- Not implemented - GUI testing would require Qt testing frameworks

## Async Testing

**pytest-asyncio (>=0.21.0) installed:**
```python
import pytest
import pytest_asyncio

@pytest_asyncio.fixture
async def async_client():
    """Async fixture for httpx client."""
    import httpx
    async with httpx.AsyncClient() as client:
        yield client

@pytest.mark.asyncio
async def test_api_call(async_client):
    """Test async API call."""
    response = await async_client.get("https://api.example.com/models")
    assert response.status_code == 200
```

## Known Testing Gaps

**At time of analysis:**
- `tests/` directory is empty
- No conftest.py exists
- No test files with `test_*.py` or `*_test.py` naming pattern found
- No pytest configuration file detected

**Recommended additions:**
- Add `pytest.ini` or `pyproject.toml` pytest section for configuration
- Add `tests/conftest.py` with shared fixtures
- Add tests for core modules:
  - `src/utils/config.py` - ConfigManager
  - `src/audio/capture.py` - AudioCapture
  - `src/database/manager.py` - DatabaseManager
  - `src/ai/openrouter.py` - OpenRouterClient

## Test Isolation

**Approach:**
- Each test should be independent
- Use fixtures for setup/teardown
- Mock file system and network calls
- Database tests should use temporary databases

---

*Testing analysis: 2026-04-14*
