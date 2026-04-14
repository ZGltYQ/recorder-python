---
phase: "02"
plan: "02"
subsystem: gui
tags: [local-llm, settings-dialog, provider-selector, ui]
dependency_graph:
  requires:
    - src/utils/config.py (LocalLLMConfig)
    - src/ai/openrouter.py (AISuggestionGenerator.set_provider)
  affects:
    - src/gui/settings_dialog.py (Local LLM settings UI)
    - src/gui/main_window.py (Provider selector)
tech_stack:
  added:
    - _create_local_llm_group() method
    - _create_openrouter_group() LocalLLMConfig import
    - load_settings() / save_settings() Local LLM handling
    - Provider selector QComboBox
    - _on_provider_changed() handler
  patterns:
    - QGroupBox with QCheckBox, QLineEdit, QSpinBox
    - Provider state management in MainWindow
key_files:
  modified:
    - src/gui/settings_dialog.py (Local LLM settings section)
    - src/gui/main_window.py (Provider selector)
decisions:
  - "Local LLM settings grouped in dedicated section after OpenRouter"
  - "Provider preference persisted to config via config.set('provider')"
  - "Status bar shows 3s notification on provider change"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-14"
---

# Phase 02 Plan 02 Summary: Local LLM Client UI

## One-liner

Added Local LLM configuration section to Settings dialog and provider selector to MainWindow AI Suggestions panel.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add Local LLM settings section to SettingsDialog | b339e0a | src/gui/settings_dialog.py |
| 2 | Add provider selector to MainWindow | b339e0a | src/gui/main_window.py |

## Changes Made

### 1. SettingsDialog (src/gui/settings_dialog.py)

Added `LocalLLMConfig` import:
```python
from ..utils.config import get_config, LocalLLMConfig
```

Added `_create_local_llm_group()` method with:
- Enable checkbox (`local_llm_enable_cb`)
- Base URL input (`local_llm_url_input`) with placeholder `http://localhost:8000/v1`
- Model name input (`local_llm_model_input`) with placeholder `local-model`
- API key input (`local_llm_key_input`) with password echo mode
- Timeout spinbox (`local_llm_timeout_spin`) range 300-3600 seconds

Updated `load_settings()` to load Local LLM config from config manager.

Updated `save_settings()` to persist Local LLM config to config manager.

### 2. MainWindow (src/gui/main_window.py)

Added provider state initialization in `__init__`:
```python
config = get_config()
self._current_provider = config.get("provider", "openrouter")
self.ai_generator = AISuggestionGenerator(provider=self._current_provider)
```

Added provider selector UI in AI Suggestions panel:
```python
provider_layout = QHBoxLayout()
provider_label = QLabel("AI Provider:")
self.provider_combo = QComboBox()
self.provider_combo.addItems(["OpenRouter", "Local"])
self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
```

Added `_on_provider_changed()` handler:
```python
def _on_provider_changed(self, text: str):
    new_provider = "openrouter" if text == "OpenRouter" else "local"
    if new_provider != self._current_provider:
        self._current_provider = new_provider
        self.ai_generator.set_provider(new_provider)
        config = get_config()
        config.set("provider", new_provider)
        self.status_bar.showMessage(f"AI Provider: {text}", 3000)
```

## Verification

```bash
grep -n "Local LLM" src/gui/settings_dialog.py | head -3
grep -n "provider_combo\|_on_provider_changed" src/gui/main_window.py | head -5
```

## Success Criteria Met

- [x] Settings dialog has Local LLM configuration section
- [x] User can enable Local LLM and configure endpoint, model, API key, timeout
- [x] Provider selector appears in MainWindow (OpenRouter/Local combo)
- [x] Switching provider updates status bar and ai_generator
- [x] Config persists Local LLM settings across app restarts

## Deviations from Plan

None - plan executed exactly as written.

## Commits

- `b339e0a`: feat(02-local-llm-client): add Local LLM settings UI and provider selector
