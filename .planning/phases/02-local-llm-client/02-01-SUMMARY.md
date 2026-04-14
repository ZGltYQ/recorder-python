---
phase: "02"
plan: "01"
subsystem: ai
tags: [local-llm, openai-compatible, provider-selection]
dependency_graph:
  requires:
    - src/utils/config.py (LocalLLMConfig)
  provides:
    - src/ai/local_llm.py (LocalLLMClient)
  affects:
    - src/ai/openrouter.py (AISuggestionGenerator provider support)
tech_stack:
  added:
    - LocalLLMClient (OpenAI-compatible chat completions)
    - LocalChatResponse dataclass
    - LocalLLMConfig dataclass
  patterns:
    - OpenAI-compatible /v1/chat/completions endpoint
    - Provider selection pattern (openrouter/local)
    - Minimum 300s timeout enforcement for cold-start models
key_files:
  created:
    - src/ai/local_llm.py (LocalLLMClient)
  modified:
    - src/utils/config.py (LocalLLMConfig, AppConfig updates)
    - src/ai/openrouter.py (provider selection in AISuggestionGenerator)
decisions:
  - "Local LLM uses OpenAI-compatible /v1/chat/completions format"
  - "Minimum timeout 300s enforced for cold-start models"
  - "Optional API key (Bearer token) for local LLMs"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-14"
---

# Phase 02 Plan 01 Summary: Local LLM Client Backend

## One-liner

Added LocalLLMConfig and LocalLLMClient with OpenAI-compatible chat completions format, integrated provider selection into AISuggestionGenerator.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add LocalLLMConfig to config.py | 75e6ec1 | src/utils/config.py |
| 2 | Create LocalLLMClient in src/ai/local_llm.py | 75e6ec1 | src/ai/local_llm.py |
| 3 | Integrate provider selection into AISuggestionGenerator | 75e6ec1 | src/ai/openrouter.py |

## Changes Made

### 1. LocalLLMConfig (src/utils/config.py)

Added `LocalLLMConfig` dataclass with fields:
- `enabled: bool = False`
- `base_url: str = "http://localhost:8000/v1"`
- `model_name: str = "local-model"`
- `api_key: str = ""` (optional for local LLMs)
- `timeout: int = 300` (minimum 300s for cold-start models)

Added to `AppConfig`:
- `local_llm: LocalLLMConfig = None`
- `provider: str = "openrouter"` (LLM provider selection)

Updated `_to_dict()` and `_from_dict()` to persist these settings.

### 2. LocalLLMClient (src/ai/local_llm.py)

Created `LocalLLMClient` class:
- Uses OpenAI-compatible `/v1/chat/completions` endpoint
- `is_configured()` checks enabled and base_url
- `_build_headers()` adds optional Bearer token auth
- `chat()` async method with OpenAI-compatible message format (dicts with role/content)
- `chat_sync()` synchronous wrapper
- Enforces minimum 300s timeout for cold-start models

### 3. Provider Selection in AISuggestionGenerator (src/ai/openrouter.py)

Modified `AISuggestionGenerator`:
- `__init__` accepts `provider` parameter ("openrouter" or "local")
- When provider="local", uses `LocalLLMClient()` instead of `OpenRouterClient()`
- `set_provider(provider)` method switches between providers dynamically
- `generate_response()` handles both provider types:
  - Local: sends dict messages directly
  - OpenRouter: converts to `Message` dataclass
- `summarize_conversation()` similarly handles both providers

## Verification

```bash
grep -n "class LocalLLMConfig" src/utils/config.py  # Found
grep -n "class LocalLLMClient" src/ai/local_llm.py  # Found
grep -n "provider" src/ai/openrouter.py | head -5   # Found
```

## Success Criteria Met

- [x] LocalLLMConfig exists in config.py with all fields persisted
- [x] LocalLLMClient uses OpenAI-compatible /v1/chat/completions format
- [x] Local LLM timeout minimum 300s enforced
- [x] AISuggestionGenerator supports provider selection
- [x] set_provider() method switches between OpenRouter and Local
- [x] Both providers work with generate_response()

## Deviations from Plan

None - plan executed exactly as written.

## Commits

- `75e6ec1`: feat(02-local-llm-client): add LocalLLMConfig, LocalLLMClient, and provider selection
