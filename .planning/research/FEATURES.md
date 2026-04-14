# Feature Research

**Domain:** Desktop audio recorder with AI-powered transcription, question detection, and new capabilities (local LLM, RAG, screenshots, priority queue)
**Researched:** 2026-04-14
**Confidence:** MEDIUM

*Note: Web search findings are LOW-MEDIUM confidence (training data may be stale). Qt documentation via Context7 is HIGH confidence.*

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Local LLM endpoint config UI | Users with local models need to configure URL + model | LOW | Simple form fields: URL, model name, API key. Existing OpenRouter UI provides pattern to follow. |
| Provider selection dropdown | Users switch between OpenRouter and local based on task | LOW | Per-conversation or global setting. Dropdown in settings and/or recording view. |
| Screenshot enable/disable toggle | Users need to control when screen capture happens | LOW | Simple checkbox in settings. Paired with interval setting. |
| Screenshot interval configuration | Different use cases need different frequencies | LOW | SpinBox or slider (seconds). Range: 5-300 seconds. Default: 30s. |
| Priority queue visual indicator | Users need to understand why some answers come faster | LOW | Badge or label showing "Priority" vs "Normal" queue. Queue count display. |
| Document upload UI | Users need to add their knowledge base | MEDIUM | File picker + drag-drop zone. Progress indicator during parsing. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable for "never miss a question" core value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| RAG document search with semantic embeddings | Questions answered from user's own documents | MEDIUM | Local embeddings via sentence-transformers. ChromaDB for vector storage. Semantic chunking recommended. |
| Screenshot AI task extraction | Capture actionable tasks visible on screen | MEDIUM | Screenshot → LLM → extract tasks. Must run async in QThread to avoid blocking audio. |
| Auto-solve detected screen tasks | Reduce manual follow-up on captured tasks | MEDIUM | AI attempts solution. Results in side panel with explanation. User can accept/dismiss. |
| Answer sourced from documents | Trust and verify AI responses | MEDIUM | Citations inline. "Answer from: DocumentName.pdf" attribution. Toggle to show/hide sources. |
| Keyword + AI dual detection queues | Fast response for obvious questions, thorough for subtle ones | MEDIUM | Keyword detection → priority queue (fast). AI detection → normal queue. Separate processing threads. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time continuous screenshot analysis | "If screenshots are good, more must be better" | Blocks audio pipeline, CPU/GPU contention, privacy concerns, low signal-to-noise | Interval-based capture (30-60s) with user-controlled enable |
| Document editing in-app | "We have the documents, might as well edit them" | Scope explosion, complex conflict resolution, not core value | Keep as upload-only. Edit in native app. |
| Multi-user/shared document collections | "Our team has shared knowledge" | Authentication complexity, sync conflicts, infrastructure | Per-user local documents. Future: optional sync service. |
| Auto-detection of all screen actions | "AI should catch everything automatically" | False positives overwhelming, performance impact, privacy | User-enabled modes with specific triggers (app-specific?) |
| Cloud document storage | "Access documents from anywhere" | Privacy violation (stated constraint: local only), infrastructure cost | Keep local. Future: optional encrypted sync. |

## Feature Dependencies

```
[Local LLM Config UI] ──required──> [LLM API Client Refactor]
                                           │
[RAG Document Upload] ──required──> [Document Parser] ──required──> [Chunking + Embeddings]
                                           │
                                           └──required──> [Vector Store (ChromaDB)]
                                           │
[RAG Search] ──requires──> [Vector Store] ──required──> [Context Injection]
                                           │
                                           └──requires──> [Answer Attribution]

[Screenshot Capture] ──required──> [AI Task Analysis] ──requires──> [Task Queue]
                                           │
                                           └──requires──> [Auto-Solve Flow]

[Keyword Detection] ──required──> [Priority Queue] ──required──> [Queue Processor]
         │                                                    │
         │                                                    └──order before──> [Normal Queue]
         │
[AI Question Detection] ──required──> [Normal Queue]
```

### Dependency Notes

- **Local LLM Config UI requires LLM API Client Refactor:** Current OpenRouterClient must be abstracted to support multiple providers with same interface.
- **RAG Document Upload requires Document Parser + Chunking + Embeddings:** Documents must be parsed, split into chunks, and embedded before search works.
- **Vector Store (ChromaDB) is required for both RAG Search and Context Injection:** All RAG features share this infrastructure.
- **Screenshot Capture requires AI Task Analysis:** Captured screenshots must be analyzed to extract tasks before they can enter any queue.
- **Priority Queue must be ordered before Normal Queue:** PRIO-03 requires priority questions get answered first, regardless of arrival order.
- **Keyword Detection conflicts with Auto-detection of all screen actions:** Keyword detection is fast and targeted; blanket auto-detection causes problems.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [ ] **Local LLM endpoint configuration** — Essential for users with privacy requirements or cost constraints. Single endpoint URL + model name field. API key optional.
- [ ] **Provider selection (OpenRouter vs Local)** — Toggle or dropdown. Per-conversation preferred for flexibility.
- [ ] **Keyword detection → priority queue** — Fast pattern match on question words ("what", "how", "why", "?" etc.) immediately puts question in priority queue.
- [ ] **Screenshot enable/disable + interval** — Simple on/off toggle with seconds configuration. Interval-based only (not continuous).
- [ ] **Document upload (single file type to start)** — Start with TXT support only. Validate pipeline before adding PDF/DOCX complexity.

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] **RAG search with context injection** — After doc upload works, add semantic search. Top-k chunks injected into AI prompt.
- [ ] **Document source attribution** — Answers that came from RAG get citation. "Answer from: DocumentX.pdf" inline.
- [ ] **AI question detection → normal queue** — Full AI analysis runs in background, enters normal queue.
- [ ] **Screenshot AI task extraction** — Analyze screenshot for actionable tasks. Parse and display extracted tasks.
- [ ] **Additional document formats** — Add PDF, MD, DOCX support after TXT validation.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Auto-solve detected screen tasks** — AI attempts solution. Requires significant UX work to present solutions acceptably.
- [ ] **Semantic chunking strategy** — Upgrade from fixed-size to semantic chunking for better retrieval quality.
- [ ] **Document chunk summaries** — Pre-compute summaries for faster retrieval and better relevance scoring.
- [ ] **App-specific screenshot filters** — Only capture certain applications (e.g., IDE, terminal) to reduce noise.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Local LLM endpoint config | HIGH | LOW | P1 |
| Provider selection dropdown | HIGH | LOW | P1 |
| Keyword → priority queue | HIGH | MEDIUM | P1 |
| Screenshot toggle + interval | HIGH | LOW | P1 |
| Document upload (TXT) | HIGH | MEDIUM | P1 |
| AI question → normal queue | MEDIUM | MEDIUM | P2 |
| RAG search + context injection | HIGH | MEDIUM | P2 |
| Document source attribution | MEDIUM | LOW | P2 |
| Screenshot AI task extraction | MEDIUM | MEDIUM | P2 |
| Auto-solve screen tasks | MEDIUM | HIGH | P3 |
| PDF/DOCX/EPUB support | MEDIUM | HIGH | P3 |
| Semantic chunking | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Otter.ai | Fireflies.ai | tl;dv | Our Approach |
|---------|----------|--------------|-------|--------------|
| Local LLM | No | No | No | **Yes** - Privacy-first, user provides endpoint |
| RAG document search | No | No | Limited | **Yes** - Full RAG pipeline with local embeddings |
| Screenshot capture | No | No | No | **Yes** - Interval-based task extraction |
| Priority queue | No | No | No | **Yes** - Keyword fast-path, AI normal path |
| Answer attribution | Inline citations | No | No | **Yes** - Document sourcing with citations |

**Competitive differentiators:**
- Local LLM support (unique among competitors)
- RAG with user documents (unique or rare)
- Screenshot-based task capture (unique)
- Dual-queue priority system (unique)

## Technical Implementation Notes

### Local LLM API

**Supported providers (OpenAI-compatible chat completions):**
- Ollama (`http://localhost:11434/v1/chat/completions`)
- LM Studio (`http://localhost:1234/v1/chat/completions`)
- LocalAI (`http://localhost:8080/v1/chat/completions`)
- Any OpenAI-compatible endpoint

**Required config parameters:**
| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| Base URL | string | Yes | — |
| Model name | string | Yes | — |
| API key | string | No | (empty for local) |
| Temperature | float | No | 0.7 |
| Max tokens | int | No | 500 |
| Timeout | int | No | 60s |

### RAG Pipeline

**Document processing:**
1. Upload via file picker or drag-drop
2. Parse document (python-docx for DOCX, PyPDF2 for PDF, etc.)
3. Chunk text (recommended: 500-1000 chars with 100 char overlap)
4. Generate embeddings (sentence-transformers `all-MiniLM-L6-v2`)
5. Store in ChromaDB with metadata (source file, page, chunk index)

**Search retrieval:**
1. Embed user question
2. Query ChromaDB for top-k (k=5 recommended) similar chunks
3. Return chunks with scores
4. Inject top chunks into AI prompt with citation metadata

### Screenshot Capture

**Qt-based approach:**
- `QScreenCapture` from Qt Multimedia (has Linux/Wayland limitations)
- Alternative: `screen().grabWindow(0)` from QWidget (simpler, works more places)
- Or: `mss` library for cross-platform performance

**Async processing requirement:**
- Screenshot capture must run in QThread worker
- Analysis (LLM call) must run in separate QThread
- Results emitted via Qt signals to main thread for UI update
- Must never block the audio capture pipeline

**Recommended interval range:**
- Minimum: 5 seconds (high-frequency for active monitoring)
- Default: 30 seconds
- Maximum: 300 seconds (5 minutes)

### Priority Queue

**Keyword patterns for fast detection:**
```
question_words = ["what", "how", "why", "when", "where", "who", "which", "?", "could", "would", "can you", "please"]
```

**Queue structure:**
```python
class QuestionQueue:
    priority: deque  # Keyword-detected questions
    normal: deque    # AI-detected questions
    
    def get_next(self) -> Question:
        if self.priority:
            return self.priority.popleft()
        return self.normal.popleft() if self.normal else None
```

**Processing order:**
1. Process all items in priority queue (FIFO)
2. Only when priority is empty, process normal queue items
3. New priority items interrupt normal queue processing

---

*Feature research for: recorder-python desktop audio recorder with local LLM, RAG, screenshots, and priority queue*
*Researched: 2026-04-14*
