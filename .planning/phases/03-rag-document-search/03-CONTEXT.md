# Phase 3: RAG Document Search - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can upload documents and receive context-augmented AI answers with citations. Documents are parsed, chunked, embedded, and stored in ChromaDB. When a question is detected (or manually triggered), relevant context is retrieved and included in the AI prompt. Answers sourced from documents show inline citations.

</domain>

<decisions>
## Implementation Decisions

### Document Management (D-01)
- **Full CRUD** — Users can upload, view, delete, and manage documents within the app

### Chunking Strategy (D-02)
- **750 characters per chunk with 15% overlap** (~112 chars) — Balanced between semantic coherence and retrieval precision

### Citation Display (D-03)
- **Inline badge format: 📄 DocumentName.txt** — Shows document icon + filename next to the answer text

### RAG + Question Flow (D-04)
- **Hybrid approach** — When documents are uploaded, RAG search is automatic on question detection. Additionally, provide a manual "Search knowledge base" button for explicit retrieval even without question detection

### Embeddings Computation (D-05)
- **Async with progress indicator** — Document indexing runs in background. Show progress bar with "Indexing document..." message. User can continue using the app while indexing completes.

### the agent's Discretion
- Chunking overlap percentage can be fine-tuned during implementation
- Exact progress bar UI styling (position, colors) — follow app conventions
- ChromaDB collection naming and metadata schema

### Folded Todos
None — no pending todos matched this phase

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs — requirements fully captured in decisions above.

### Internal References
- `.planning/ROADMAP.md` §Phase 3 — Phase goal and success criteria
- `.planning/PROJECT.md` — Core value: "Capture conversations and never miss a question that can be answered"
- `.planning/STATE.md` §Decisions — Phase 2 decision: Local LLM uses OpenAI-compatible chat completions format

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/speech/asr.py` — TranscriptionResult dataclass pattern for chunking strategy
- `src/ai/openrouter.py` — OpenRouterClient for LLM integration (already handles prompts)

### Established Patterns
- Qt signals for async operations (from AudioCapture, TranscriptionManager)
- QThread for background work that shouldn't block audio pipeline
- Structured logging via structlog

### Integration Points
- RAG module connects to: OpenRouterClient (for AI answering), DatabaseManager (for conversation history), MainWindow (for UI signals)
- Embeddings → ChromaDB → OpenRouter prompt injection → UI citation display

</code_context>

<specifics>
## Specific Ideas

- Citation should be visually distinct but not intrusive — inline badge near answer
- Progress indicator should be dismissible or auto-hide on completion
- Manual "Search knowledge base" button should be clearly visible but not dominant

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-rag-document-search*
*Context gathered: 2026-04-14*
