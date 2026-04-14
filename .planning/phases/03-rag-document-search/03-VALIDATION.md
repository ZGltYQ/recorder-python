---
phase: 03
slug: rag-document-search
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 3 — RAG Document Search - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pytest.ini` or `pyproject.toml` (Wave 0 creates if missing) |
| **Quick run command** | `pytest tests/test_rag.py -v --tb=short` |
| **Full suite command** | `pytest tests/ -v --tb=short -k "rag"` |
| **Estimated runtime** | ~30-60 seconds (embedding model loads once) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_rag.py -v --tb=short`
- **After every plan wave:** Run `pytest tests/ -v --tb=short -k "rag"`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds (embedding model loading is expensive)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | RAG-02 | T-03-01 | N/A | unit | `pytest tests/test_rag.py::test_chunker -v` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | RAG-01, RAG-02 | T-03-01 | Validate file type | unit | `pytest tests/test_rag.py::test_document_upload -v` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | RAG-03, RAG-04 | T-03-01 | N/A | integration | `pytest tests/test_rag.py::test_embedding_worker -v` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | RAG-05, RAG-06 | T-03-02 | Validate context injection | unit | `pytest tests/test_rag.py::test_rag_search -v` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | RAG-07 | T-03-03 | Sanitize citation format | unit | `pytest tests/test_rag.py::test_citation_format -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_rag.py` — test stubs for chunking, upload, embedding, search, citation
- [ ] `tests/conftest.py` — shared fixtures (mock_chromadb, mock_embedding_model)
- [ ] `pytest.ini` or `pyproject.toml` — pytest configuration if not existing

*If none: "Existing infrastructure covers all phase requirements."*

### Wave 0 Test Stubs

```python
# tests/test_rag.py

import pytest

def test_chunker():
    """RAG-02: Verify 750 char chunks with 15% overlap."""
    pass

def test_document_upload():
    """RAG-01: Verify TXT file parsing."""
    pass

def test_embedding_worker():
    """RAG-03: Verify embedding dimension = 384."""
    pass

def test_rag_search():
    """RAG-05, RAG-06: Verify context injection into prompt."""
    pass

def test_citation_format():
    """RAG-07: Verify 📄 DocumentName.txt format."""
    pass
```

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Drag-drop zone visual | RAG-01 | PySide6 widget rendering | Run app, drag TXT file onto drop zone, verify highlight effect |
| Progress bar during indexing | RAG-05 | UI feedback loop | Upload large doc, verify progress bar updates |
| Citation badge appearance | RAG-07 | Visual styling | Ask question with context, verify badge styling matches app theme |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** {pending / approved YYYY-MM-DD}
