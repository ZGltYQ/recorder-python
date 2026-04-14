# Coding Conventions

**Analysis Date:** 2026-04-14

## Languages

**Primary:**
- Python 3.10+ - All application code

## Code Style

**Formatter:** Black
- Line length: 100 characters
- Target version: Python 3.10

**Linter:** Ruff
- Line length: 100 characters
- Target version: Python 3.10
- Selects: E, F, I, N, W, UP, B, C4, SIM

**Type Checker:** MyPy
- Python version: 3.10
- `warn_return_any = true`
- `disallow_untyped_defs = true`

## Naming Patterns

**Files:**
- Python modules: `snake_case.py`
- Example: `audio_capture.py`, `openrouter.py`

**Classes:**
- PascalCase
- Example: `AudioCapture`, `TranscriptionManager`, `OpenRouterClient`

**Functions/Methods:**
- snake_case
- Example: `list_sources()`, `get_available_models()`, `transcribe_audio()`

**Variables:**
- snake_case
- Example: `source_name`, `audio_data`, `is_recording`

**Constants:**
- SCREAMING_SNAKE_CASE for module-level constants
- Example: `BASE_URL`, `AVAILABLE_MODELS`

**Private Members:**
- Prefix with underscore: `_capture_thread`, `_is_recording`

**Dataclasses:**
- PascalCase name, snake_case fields
- Example: `AudioSource`, `TranscriptionResult`

## Import Organization

**Order (per Ruff rules):**
1. E - Errors
2. F - Pyflakes
3. I - Imports (isort)
4. N - Naming conventions
5. W - Whitespace
6. UP - Python upgrade
7. B - Flake8-bugbear
8. C4 - Perflint
9. SIM - Simplifications

**Relative Imports:**
- Use `from ..utils.logger import get_logger` for sibling modules
- Use `from ..audio.capture import AudioCapture` for sibling packages

## Error Handling

**Pattern:**
```python
try:
    # operation
except Exception as e:
    logger.error("Failed operation", error=str(e))
    return None  # or emit error signal
```

**Logging Errors:**
- Use structlog with structured context
- Always include error details: `logger.error("Operation failed", error=str(e))`

**Signals for GUI Errors:**
- QObject signals emit error strings: `self.error.emit(str(e))`
- GUI slots receive and display errors

## Logging

**Framework:** structlog

**Pattern:**
```python
from ..utils.logger import get_logger
logger = get_logger(__name__)
```

**Structured Logging:**
```python
logger.info("Audio capture started", source=source_name)
logger.error("Failed to list sources", error=str(e))
```

## Comments

**Docstrings:**
- Module-level: """Description of module."""
- Class-level: Use docstrings for public classes
- Method-level: Document public methods

**Example:**
```python
class AudioCapture(QObject):
    """Manages audio capture from PipeWire/PulseAudio sources."""
```

## Function Design

**Size:** Functions tend to be focused (30-100 lines typical)

**Parameters:** Explicit typing with default values

**Return Values:**
- Return `Optional[T]` when may return None
- Return `bool` for success/failure operations
- Use signals for async GUI notifications

## Module Design

**Public API:** Classes are exported, functions as needed

**Singletons:** Global instances via getter functions
```python
_config: Optional[ConfigManager] = None

def get_config() -> ConfigManager:
    """Get the global configuration manager."""
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config
```

**Dataclasses:** Used for data transfer objects
```python
@dataclass
class TranscriptionResult:
    text: str
    timestamp: float
    is_final: bool
    speaker: Optional[str] = None
```

## Signal/Slot Pattern (PySide6)

**For Qt Signals:**
```python
from PySide6.QtCore import QObject, Signal

class MyClass(QObject):
    error = Signal(str)
    data_ready = Signal(np.ndarray)
```

## Async Patterns

**Async/Await with httpx:**
```python
async def get_available_models(self) -> List[ModelInfo]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        return response.json()
```

**Sync Wrappers:**
```python
def get_available_models_sync(self, force_refresh: bool = False) -> List[ModelInfo]:
    import asyncio
    return asyncio.run(self.get_available_models(force_refresh))
```

## Type Annotations

**Required per mypy config:**
- All functions must have type annotations
- Use `Optional[T]` for nullable types
- Use `Union[T1, T2]` for multiple types

**Example:**
```python
def transcribe_audio(
    self,
    audio_data: Union[np.ndarray, str, Path],
    sample_rate: int = 16000,
    language: Optional[str] = None,
) -> Optional[TranscriptionResult]:
```

---

*Convention analysis: 2026-04-14*
