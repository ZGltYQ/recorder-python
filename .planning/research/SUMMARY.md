# Project Research Summary

**Project:** recorder-python
**Domain:** Desktop Audio Recorder with LLM, RAG, Screenshot Analysis, and Priority Queue
**Researched:** 2026-04-14
**Confidence:** MEDIUM

## Executive Summary

This is a PySide6 desktop audio recorder being extended with AI-powered features: local LLM API support, RAG-based document search, interval screenshot capture with task extraction, and a priority queue for question answering. The application uses an existing Qt signal/slot event-driven architecture, which these features extend naturally via new components that emit Qt signals for async results.

The recommended approach follows a four-phase build order: **Priority Queue → Local LLM Client → RAG Module → Screenshot Mode**. This order respects dependencies (priority queue is used by all AI features, LLM client is needed for RAG and screenshot analysis) while validating each piece before adding the next. Key risks include hardcoded timeout values for local LLMs (which have cold-start latency), naive fixed-size chunking degrading RAG retrieval, and screenshot storage bloat if retention policies aren't implemented from day one.

**Overall confidence: MEDIUM** — Qt threading patterns and asyncio are well-documented (HIGH confidence), but RAG implementation details and local LLM provider quirks rely on community sources with limited verification (MEDIUM).

---

## Key Findings

### Recommended Stack

The stack extends existing httpx and PySide6 with sentence-transformers for embeddings, ChromaDB for local vector storage, and Docling for unified document parsing. Screenshot capture uses Qt's built-in QScreenCapture/QWindowCapture APIs. The asyncio.PriorityQueue stdlib component handles priority task queuing without external dependencies.

**Core technologies:**
- **httpx 0.27.0+** — async HTTP client for all LLM API calls (OpenRouter and local endpoints share the same interface)
- **sentence-transformers 3.0.0+** — embeddings via `all-MiniLM-L6-v2` (384-dim, fast, effective for semantic search)
- **ChromaDB 0.5.0+** — local-first vector database with persistent storage (FAISS alternative if needed at scale)
- **Docling 2.0.0+** — unified document parser for PDF, DOCX, PPTX, XLSX, HTML, EPUB, ODT, RTF (IBM-backed, MIT-licensed)
- **PySide6.QtMultimedia** — screen capture via `QScreenCapture`/`QWindowCapture`, native fit for existing PySide6 app
- **asyncio.PriorityQueue** — stdlib priority queue accepting `(priority, item)` tuples, lower int = higher priority

### Expected Features

**Must have (table stakes):**
- Local LLM endpoint configuration UI (URL, model name, optional API key)
- Provider selection dropdown (OpenRouter vs Local, per-conversation)
- Screenshot enable/disable toggle with interval configuration (5-300 seconds, default 30s)
- Priority queue visual indicator (badge showing Priority vs Normal queue depth)
- Document upload UI (file picker + drag-drop with progress)

**Should have (competitive differentiators):**
- RAG document search with semantic embeddings — answers from user's own documents
- Screenshot AI task extraction — captures actionable tasks visible on screen
- Answer sourced from documents — inline citations with "Answer from: DocumentName.pdf"
- Keyword + AI dual detection queues — fast response for obvious questions, thorough for subtle ones

**Defer (v2+):**
- Auto-solve detected screen tasks — requires significant UX work for acceptable presentation
- Semantic chunking strategy — upgrade from fixed-size after validating core retrieval
- PDF/DOCX/EPUB support — validate with TXT first before adding format complexity

### Architecture Approach

The architecture extends the existing Qt signal/slot event-driven model. New components fit into the AI layer: `LLMClientFactory` selects between OpenRouter and local endpoints, `RAGRetriever` provides document retrieval as a service, `ScreenshotCapture` runs in its own QThread to avoid blocking recording, and `PriorityAnswerQueue` uses asyncio for request handling. Key patterns include factory pattern for LLM providers, QThread worker for screenshots, and asyncio.PriorityQueue for request prioritization.

**Major components:**
1. **LLMClientFactory** — creates LLM client based on provider selection (OpenRouter/Local)
2. **RAGRetriever** — stores documents, generates embeddings, retrieves context for AI prompts
3. **ScreenshotCapture** — captures screenshots on interval in QThread, emits signals with pixmaps
4. **PriorityAnswerQueue** — manages priority queue using asyncio.PriorityQueue with HIGH/NORMAL levels

### Critical Pitfalls

1. **Hardcoded timeout values for local LLMs** — Cold-loaded local models take 2-5 minutes for first token. Use configurable minimum 300s timeout for first inference, progressive timeout approach. Address in LLM-03.

2. **Assuming OpenAI-compatible API means identical behavior** — Local providers lack `function_call`/`tool_use`, may handle streaming differently, don't support `max_tokens` in some cases. Create abstraction layer, test each provider's response shape. Address in LLM-03.

3. **Naive fixed-size chunking in RAG** — Splitting mid-sentence/paragraph breaks semantic coherence. Use semantic chunking (by natural boundaries), preserve metadata. Address in RAG-02 before production.

4. **Embedding drift after model updates** — New embedding model = different vector space. Store model version with documents, implement re-indexing strategy. Address in RAG-02.

5. **Screenshot storage bloat** — Unbounded disk consumption if screenshots never deleted. Implement retention policy, use circular buffer, show storage in UI. Address in SCRN-02.

---

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Priority Queue Foundation
**Rationale:** All subsequent AI features submit requests through the priority queue. Building this first validates the async pattern before integrating with LLM or RAG.

**Delivers:** `src/ai/priority_queue.py` with HIGH/NORMAL priority levels, starvation prevention, monitoring endpoints

**Implements:** asyncio.PriorityQueue with priority aging mechanism

**Avoids:** Priority starvation pitfall (PRIO-03) — must build aging in from start

---

### Phase 2: Local LLM Client
**Rationale:** Uses priority queue for request handling. Depends on priority queue but not on RAG or screenshot features.

**Delivers:** `src/ai/local_llm.py`, `src/ai/llm_factory.py`, Local LLM config UI in settings

**Uses:** httpx for async HTTP, OpenAI-compatible endpoint format

**Implements:** LLMClientFactory with OpenRouter and LocalLLM providers

**Avoids:** Hardcoded timeout pitfall (use 300s minimum), OpenAI-compatible ≠ identical pitfall (abstraction layer normalizes responses)

---

### Phase 3: RAG Module
**Rationale:** Depends on LLM client for prompt augmentation. Document ingestion can be validated independently before screenshot integration.

**Delivers:** `src/rag/` module with DocumentStore, Embedder, Chunking, Retrieval

**Uses:** sentence-transformers, ChromaDB, semantic chunking strategy

**Implements:** RAGRetriever with embedding model versioning, hybrid search ready

**Avoids:** Naive chunking pitfall (semantic boundaries from start), embedding drift pitfall (version stored with documents)

---

### Phase 4: Screenshot Mode
**Rationale:** Uses LLM client and priority queue. Most complex integration with UI threading concerns.

**Delivers:** `src/screenshot/` module with QThread capture, async analysis, retention policy

**Implements:** ScreenshotCapture in QThread, ScreenshotAnalyzer with confidence thresholds

**Avoids:** Screenshot storage bloat (retention policy + circular buffer), blocking audio pipeline (QThread isolation)

---

### Phase Ordering Rationale

1. **Priority Queue first** — None of the new AI features make sense without prioritization. asyncio.PriorityQueue is stdlib, no new external dependencies to validate.

2. **Local LLM second** — Local LLM only needs the priority queue. Can validate provider abstraction before adding document processing complexity.

3. **RAG third** — RAG needs LLM client for context injection. Document ingestion is independent of screenshot features.

4. **Screenshot last** — Most complex threading model (QThread + asyncio + Qt signals). Depends on LLM client and priority queue.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (RAG):** Semantic chunking implementation details, embedding model selection tradeoffs — may need `/gsd-research-phase` for RAG chunking strategies
- **Phase 4 (Screenshot):** QScreenCapture platform limitations on Wayland/Linux — needs platform-specific fallback research

Phases with standard patterns (skip research-phase):
- **Phase 1 (Priority Queue):** asyncio.PriorityQueue is stdlib, well-documented
- **Phase 2 (Local LLM):** Ollama OpenAI compatibility is documented, factory pattern is standard

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Technologies are well-documented, existing codebase already uses httpx/PySide6 |
| Features | MEDIUM | Web search findings have stale data risk; Qt docs via Context7 are HIGH |
| Architecture | HIGH | Qt threading and asyncio patterns are standard, documented in official sources |
| Pitfalls | MEDIUM | Community sources agree on major pitfalls; some (embedding drift) less validated |

**Overall confidence:** MEDIUM

### Gaps to Address

- **Local LLM provider quirks:** Research was based on Ollama compatibility docs. Other providers (LM Studio, LocalAI) may have different edge cases. Validate during Phase 2 implementation.

- **RAG evaluation methodology:** No established benchmark for retrieval quality in this specific domain. Need to define "good enough" retrieval for the use case during Phase 3.

- **Screenshot confidence thresholds:** No research on appropriate thresholds for task detection false positives. Will need empirical tuning during Phase 4.

---

## Sources

### Primary (HIGH confidence)
- Context7 `/encode/httpx` — AsyncClient, streaming patterns
- Context7 `/pythonguis/pyside6` — Qt threading best practices
- Qt for Python Docs (doc.qt.io) — QScreenCapture API
- Python stdlib `asyncio-queue.html` — PriorityQueue documentation

### Secondary (MEDIUM confidence)
- Ollama OpenAI Compatibility (ollama.com) — API format, behavioral differences
- RAG Architecture Patterns (python.plainenglish.io) — Chunking strategies, embedding drift
- Elder Scripts (theeldersscripts.com) — LLM timeout issues in production

### Tertiary (LOW confidence)
- Reddit r/LLMDevs — Embedding drift discussion, needs official source validation
- Web search findings — Screenshot patterns, ChromaDB vs FAISS comparisons

---
*Research completed: 2026-04-14*
*Ready for roadmap: yes*