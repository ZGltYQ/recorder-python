# Requirements: recorder-python

**Defined:** 2026-04-14
**Core Value:** Capture conversations and never miss a question that can be answered.

## v1 Requirements

### Local LLM API

- [ ] **LLM-01**: User can configure custom LLM API endpoint (base URL, model name, optional API key)
- [ ] **LLM-02**: User can select which LLM provider to use per conversation (OpenRouter or Local)
- [ ] **LLM-03**: App calls local LLM API with OpenAI-compatible chat completions format
- [ ] **LLM-04**: Local LLM timeout configurable (minimum 300s for cold-start models)

### Priority Queue

- [ ] **PRIO-01**: Keyword-detected questions enter priority answer queue (fast path)
- [ ] **PRIO-02**: Background AI-detected questions enter normal queue
- [ ] **PRIO-03**: Priority queue answered before normal queue (starvation prevention via aging)
- [ ] **PRIO-04**: Queue depth displayed in UI (priority vs normal count)

### Document Upload (RAG)

- [ ] **RAG-01**: User can upload TXT documents via file picker or drag-drop
- [ ] **RAG-02**: Uploaded documents parsed and chunked (500-1000 chars with overlap)
- [ ] **RAG-03**: Document chunks embedded with sentence-transformers (all-MiniLM-L6-v2)
- [ ] **RAG-04**: Embeddings stored in ChromaDB with source metadata
- [ ] **RAG-05**: When question detected, app searches document knowledge base (top-k retrieval)
- [ ] **RAG-06**: Relevant document context included in AI prompt for answering
- [ ] **RAG-07**: Answers sourced from documents show inline citation ("Answer from: DocumentName.pdf")

### Screenshot Mode

- [ ] **SCRN-01**: User can enable screenshot mode with configurable interval (5-300 seconds, default 30s)
- [ ] **SCRN-02**: App captures screenshot at configured interval (runs in QThread, never blocks audio pipeline)
- [ ] **SCRN-03**: Screenshot analyzed by AI for actionable tasks
- [ ] **SCRN-04**: Detected tasks auto-solved by AI
- [ ] **SCRN-05**: Task solutions displayed in side panel with explanation
- [ ] **SCRN-06**: Screenshot storage has retention policy (circular buffer, configurable max count)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Additional Document Formats

- **RAG-08**: User can upload PDF documents
- **RAG-09**: User can upload DOCX, ODT, RTF documents
- **RAG-10**: User can upload MD, EPUB documents

### Advanced RAG

- **RAG-11**: Semantic chunking strategy (chunk by natural boundaries vs fixed-size)
- **RAG-12**: Embedding model versioning (detect drift, offer re-indexing)

### Screenshot Enhancement

- **SCRN-07**: Screenshot storage display in UI (count, disk usage)
- **SCRN-08**: User can manually trigger screenshot capture

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| App hosting/running local LLM models | User provides API endpoint only |
| TTS/speech output | Answers displayed only in side panel |
| Video recording | Screenshots are image captures only |
| Document editing | Upload and search only |
| Real-time continuous screenshot analysis | Blocks audio pipeline, privacy concerns |
| Multi-user/shared document collections | Per-user local documents only |
| Cloud document storage | Privacy constraint: all local |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LLM-01 | Phase 2 | Pending |
| LLM-02 | Phase 2 | Pending |
| LLM-03 | Phase 2 | Pending |
| LLM-04 | Phase 2 | Pending |
| PRIO-01 | Phase 1 | Pending |
| PRIO-02 | Phase 1 | Pending |
| PRIO-03 | Phase 1 | Pending |
| PRIO-04 | Phase 1 | Pending |
| RAG-01 | Phase 3 | Pending |
| RAG-02 | Phase 3 | Pending |
| RAG-03 | Phase 3 | Pending |
| RAG-04 | Phase 3 | Pending |
| RAG-05 | Phase 3 | Pending |
| RAG-06 | Phase 3 | Pending |
| RAG-07 | Phase 3 | Pending |
| SCRN-01 | Phase 4 | Pending |
| SCRN-02 | Phase 4 | Pending |
| SCRN-03 | Phase 4 | Pending |
| SCRN-04 | Phase 4 | Pending |
| SCRN-05 | Phase 4 | Pending |
| SCRN-06 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-04-14 after initial definition*
