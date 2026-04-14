# Pitfalls Research

**Domain:** Local LLM API, RAG, Screenshot Automation, Priority Queues
**Researched:** 2026-04-14
**Confidence:** MEDIUM

## Critical Pitfalls

### Pitfall 1: Hardcoded Timeout Values for Local LLMs

**What goes wrong:**
API calls to local LLMs (Ollama, LM Studio, etc.) hang indefinitely or fail after 60 seconds even when a much higher timeout is configured. Cold-loaded local models legitimately take longer to generate responses than cloud APIs, but the application aborts prematurely.

**Why it happens:**
- Developers copy timeout values from OpenAI API patterns (typically 30-120s)
- Local models on first inference load weights into GPU memory, causing 2-5 minute first-token latency
- Ollama and similar tools have internal timeout mechanisms separate from HTTP client timeouts
- "Connection reset by peer" errors occur when client gives up before model finishes loading

**How to avoid:**
- Use configurable timeouts with minimum 300s for first inference on local models
- Implement progressive timeout: short for first token, longer for full generation
- Add endpoint availability check before issuing request
- Handle 504 Gateway Timeout as "model loading" not "model unavailable"

**Warning signs:**
- Logs show "Timeout exceeded" immediately after request
- First request always fails, subsequent requests succeed
- Model loading messages in Ollama logs but application sees immediate failure

**Phase to address:**
LLM-03 (Local LLM API integration) — timeouts must be designed before first integration test

---

### Pitfall 2: Assuming OpenAI-Compatible API Means Identical Behavior

**What goes wrong:**
Application makes requests using OpenAI API format but local LLM provider (Ollama, vLLM, LM Studio) returns responses in slightly different shapes, doesn't support streaming correctly, or lacks certain fields. Requests fail silently or return malformed responses.

**Why it happens:**
- "OpenAI-compatible" means basic endpoint structure matches, not full behavioral parity
- Local providers often lack `function_call` / `tool_use` support
- Streaming responses may use different SSE format or chunk structure
- Some providers don't support `max_tokens` parameter
- Model names may need provider-specific prefixes (e.g., `ollama/llama2` vs `llama2`)

**How to avoid:**
- Create abstraction layer that normalizes responses
- Test each provider's response shape before building integration
- Verify streaming works by testing with small outputs first
- Handle missing optional fields gracefully with defaults
- Don't assume API key handling is identical (some local APIs use no key or different header)

**Warning signs:**
- Response parsing errors in logs for specific providers
- Streaming responses malformed (JSON broken across chunks)
- Function calling works on OpenRouter but not local provider

**Phase to address:**
LLM-03 — build provider abstraction during initial local LLM integration

---

### Pitfall 3: Naive Fixed-Size Chunking in RAG

**What goes wrong:**
Documents are chunked into fixed-size pieces (e.g., 512 tokens) regardless of semantic boundaries. Related information gets split across chunks, losing context. Unrelated information gets combined, diluting relevance. Retrieval returns fragments that don't make sense alone.

**Why it happens:**
- Simple to implement: split by character count or token count
- Developers don't consider that sentences and paragraphs have semantic meaning
- Code splits mid-sentence, mid-thought, mid-definition
- Fixed chunks ignore document structure (headers, lists, code blocks)

**How to avoid:**
- Use semantic chunking: split by natural boundaries (sentences, paragraphs, code blocks)
- Implement parent-child chunking: small chunks for retrieval precision, large parent chunks for context
- Preserve metadata (headers, page numbers, document title) with each chunk
- For code: chunk by function/class, not by arbitrary line count
- For legal/technical docs: chunk by section/clause, preserving definitions

**Warning signs:**
- Retrieved chunks feel incomplete when read
- Answers reference information not present in retrieved chunk
- Chunking code contains `chunk_size = 512` with no explanation
- No distinction between chunk strategies for different document types

**Phase to address:**
RAG-02 (Document parsing and storage) — chunking strategy is foundational, changing later requires re-indexing

---

### Pitfall 4: Embedding Drift After Model Updates

**What goes wrong:**
RAG retrieval accuracy degrades over time even though documents haven't changed. Semantic search returns irrelevant results. The embedding space has "drifted" because the embedding model was updated.

**Why it happens:**
- Embedding models are updated periodically (every few months)
- New model produces vectors in different space than old model
- Old document embeddings stored in database no longer match query embeddings
- Similarity scores become meaningless across the model boundary

**How to avoid:**
- Store embedding model version with each document/chunk
- Store embedding model version in retrieval results
- When model updates: either re-embed all documents, or use hybrid search (keyword + vector)
- Monitor retrieval quality over time with eval queries
- Version embeddings and treat them as immutable — new model = new embedding version

**Warning signs:**
- Same query returns different results after model update
- Retrieval latency increases after model swap (new vectors are longer/wider)
- No documentation of embedding model version in deployment
- RAG evaluation metrics decline without document changes

**Phase to address:**
RAG-02 — embed model versioning must be designed upfront; re-indexing strategy needed before production

---

### Pitfall 5: Screenshot Storage Bloat

**What goes wrong:**
Application captures screenshots at configured interval (e.g., every 5 seconds) but never deletes them. After a day of running, gigabytes of storage are consumed. After a week, the disk is full and recording stops.

**Why it happens:**
- Screenshots saved to disk without retention policy
- No automatic cleanup of old screenshots
- User has no visibility into screenshot storage usage
- Screenshot analysis happens async but files aren't deleted after processing
- Error paths skip cleanup (exception during analysis leaves file on disk)

**How to avoid:**
- Implement screenshot retention policy (keep last N screenshots, or last N hours)
- Store screenshots in memory for processing, not disk when possible
- If disk storage needed: use circular buffer or time-based eviction
- Delete screenshots immediately after AI analysis completes
- Show storage usage in UI and allow user to set retention limits
- Set system temp directory with cleanup on startup

**Warning signs:**
- Screenshot directory grows unbounded (monitor disk usage)
- No screenshot retention configuration in settings
- Screenshots older than processing timestamp still exist
- No cleanup job or cron for old screenshots

**Phase to address:**
SCRN-02 (Screenshot capture) — storage strategy must be designed alongside capture, not added later

---

### Pitfall 6: False Positive Task Detection from Screenshots

**What goes wrong:**
AI analyzes screenshot and detects a "task" that isn't actually actionable. System attempts to solve a non-existent problem. User sees incorrect or confusing automated actions. Trust in the feature erodes.

**Why it happens:**
- UI elements that look clickable aren't (disabled buttons, decorative elements)
- Temporal UI changes (loading spinners, animations) detected as tasks
- Text that looks like a form field isn't editable
- Modal dialogs detected as main content
- Dark mode vs light mode creates false differences
- Notification popups treated as primary actions

**How to avoid:**
- Combine screenshot analysis with accessibility tree when possible
- Require multiple consecutive screenshot detections before flagging as task
- Add confidence threshold — don't act on low-confidence detections
- Implement "confirmation before action" for ambiguous cases
- Allow user to train/fine-tune detection on their specific applications
- Ignore transient UI states (loading, animating, notifications)

**Warning signs:**
- Detected tasks don't match what user was actually doing
- AI responds to already-resolved UI states
- Detection works in demo but fails on user's specific apps
- No confidence scoring on detected tasks

**Phase to address:**
SCRN-03 (Screenshot analyzed for tasks) — detection threshold tuning is an ongoing concern, start conservative

---

### Pitfall 7: Priority Queue Starvation

**What goes wrong:**
Low-priority items in the queue never get processed. Keyword-detected questions (priority) keep arriving and always take precedence. Background AI-detected questions (normal) sit in queue forever. Users wonder why some features never work.

**Why it happens:**
- Priority queue only dequeues high-priority items when empty
- New high-priority items arrive faster than they can be processed
- Low-priority items never reach the front because new priority items keep jumping ahead
- No aging mechanism to boost priority of stale low-priority items

**How to avoid:**
- Implement priority queue with guaranteed service: eventually all items processed
- Use priority aging — low-priority items increase in priority the longer they wait
- Process items in batches: drain all priority, then process some normal, then back to priority
- Set maximum wait time for low-priority items before forced processing
- Monitor queue depths separately for each priority level

**Warning signs:**
- Normal-priority queue depth grows unbounded while priority queue stays near empty
- Users report "answers never come" for certain questions
- Queue monitoring shows 100% priority items, 0% normal items processed
- Low-priority items show timestamps hours/days old

**Phase to address:**
PRIO-03 (Priority queue processing) — starvation prevention must be built into queue design

---

### Pitfall 8: Priority Inversion in Queue Processing

**What goes wrong:**
High-priority task blocks because a low-priority task holds a shared resource (database connection, API client, file lock) needed by the high-priority task. The high-priority task waits while the low-priority task continues slowly. System appears frozen for high-priority work.

**Why it happens:**
- Queue processing uses shared resources without priority-aware locking
- High-priority worker thread waits for lock held by low-priority worker
- Low-priority task acquires exclusive resource then gets preempted by higher-priority system tasks
- Resource cleanup happens in wrong order causing deadlock

**How to avoid:**
- Use priority inheritance: low-priority task holding resource temporarily gets boosted to high priority
- Avoid exclusive locks in queue processing — use lock-free data structures
- Keep resource acquisition short and predictable
- Process priority items in dedicated threads with isolated resources
- Use priority-aware thread pool: high-priority tasks get threads first

**Warning signs:**
- High-priority tasks sometimes take 10x longer than expected
- Logs show high-priority task waiting on "resource busy"
- Occasional deadlocks in multi-step processing
- Queue processing time increases when both priority levels active

**Phase to address:**
PRIO-03 — architecture review needed before implementing queue processing

---

### Pitfall 9: Screenshot Analysis Blocks Audio Recording Pipeline

**What goes wrong:**
Application freezes or drops audio while AI analyzes a screenshot. Recording becomes choppy or stops entirely. Question detection fails because audio processing is blocked. The feature designed to help breaks the core recording functionality.

**Why it happens:**
- Screenshot analysis runs on main Qt event loop
- AI analysis is CPU/GPU intensive and blocks
- No async/background processing for screenshots
- Qt signals/slots blocked during synchronous AI call
- Thread priority not set correctly — screenshot thread competes with audio thread

**How to avoid:**
- Always process screenshots in separate thread/process from audio pipeline
- Use Qt's threading primitives correctly: QThread for long-running tasks
- Set audio processing thread to higher priority than screenshot analysis
- Never call AI APIs synchronously from audio/capture threads
- Implement backpressure: if screenshot queue fills up, drop oldest or skip analysis

**Warning signs:**
- Audio drops/corruption when screenshot analysis runs
- Main window becomes unresponsive during screenshot analysis
- CPU usage spikes to 100% on all cores during screenshot capture
- Audio buffer overflow errors coincide with screenshot capture times

**Phase to address:**
SCRN-03 — threading model must be designed before screenshot analysis implementation

---

### Pitfall 10: RAG Retrieval Returns Out-of-Context Information

**What goes wrong:**
RAG system retrieves document chunks that are technically relevant to query but don't actually answer the question. AI generates answer based on retrieved context that doesn't address what was asked. User gets plausible but wrong information.

**Why it happens:**
- Chunking breaks causal chains (A causes B causes C, all in different chunks)
- Keyword similarity drives retrieval, not semantic relevance
- Retrieved chunks lack sufficient context to be understood alone
- No re-ranker to evaluate retrieved chunks against query
- Top-k retrieval returns k most similar but not k most relevant

**How to avoid:**
- Implement re-ranking: retrieve 20 chunks, rerank to top 5
- Use query expansion: reformulate user question to match document style
- Store surrounding context with each chunk (previous chunk, section header)
- Add hybrid retrieval: combine keyword search (BM25) with vector search
- Evaluate retrieval quality with domain-specific questions, not generic benchmarks

**Warning signs:**
- Answers cite sources that don't fully support the claim
- Users ask "where did that come from?" — sources are tangentially related
- Retrieval evaluation shows high similarity scores but low relevance ratings
- No reranking step in retrieval pipeline

**Phase to address:**
RAG-03 (Document search on question detection) — reranking is essential for accuracy, not optional enhancement

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Fixed 512-token chunking | Simple to implement | Poor retrieval accuracy, semantic breakage | MVP only, must plan migration |
| No embedding versioning | Faster initial development | Silent accuracy degradation after model updates | Never for production |
| Screenshots to disk | Easier debugging | Storage bloat, performance overhead | Debug builds only |
| Single timeout for all LLM calls | Simpler code | Local models always fail | Never — needs progressive timeout |
| SQLite for document embeddings | Simple setup | Poor vector search performance at scale | <1000 documents only |
| No priority queue monitoring | Faster to ship | Silent starvation, user confusion | Never for production |
| Synchronous AI calls | Easier to write | Blocks entire application | Never in main pipeline |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Ollama API | Sending OpenAI `functions` parameter | Use Ollama's native tool calling or omit |
| Ollama API | Not handling `model` prefix (need `ollama/llama2`) | Test with actual model name format first |
| Local LLM | Hardcoding 60s timeout | Start at 300s for first inference, 120s after |
| Local LLM | Assuming streaming works like OpenAI | Test streaming with real output before building UI |
| RAG Embedding | Storing only vector, no source reference | Store chunk text + source document + page number |
| RAG Embedding | Re-embedding on every query | Cache embeddings, only re-embed new/changed docs |
| Screenshot Storage | Saving to app directory | Use system temp or user-configurable path |
| Screenshot Analysis | Blocking on AI response | Always async with timeout |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Unbounded screenshot queue | Memory grows, UI lags | Set max queue size, drop oldest | >30 seconds of screenshots queued |
| Re-ranking all results | Latency spikes on every query | Cache reranker scores, limit rerank candidates | >100 documents indexed |
| No embedding batching | Slow document ingestion | Batch embed requests (16-64 chunks at a time) | >100 documents to index |
| Queue processing without backpressure | Memory exhaustion | Reject new items when queue full | >1000 items in queue |
| Synchronous LLM calls in Qt thread | UI freezes | All LLM calls in QThreadPool workers | Every screenshot analysis |
| No connection pooling for LLM | Slow subsequent requests | Reuse HTTP connection | Every request on local models |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Local LLM API key in config file | Others with file access can use quota | Use system keyring or environment variables |
| Screenshots saved with predictable names | Privacy leak if path discovered | Use UUID filenames, secure temp directory |
| No HTTPS for local LLM API | Local network eavesdropping | Localhost is generally safe, but add cert verification for production |
| Storing document embeddings without encryption | Sensitive document content in plain DB | Documents are user-uploaded — apply same protections as originals |
| LLM prompt injection from RAG | Malicious document content alters behavior | Sanitize/validate retrieved chunks before adding to prompt |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No feedback during screenshot analysis | User doesn't know if feature works | Show "analyzing screenshot" indicator |
| Unknown storage usage | Disk fills without warning | Show storage stats in settings, warn at 80% capacity |
| False positive task detection | AI "fixes" things that aren't problems | Always confirm before acting, allow undo |
| Starved normal-priority queue | Some features seem broken | Show queue status, allow manual priority override |
| No LLM connection status | User doesn't know if local LLM is running | Show provider status in UI (connected/disconnected/error) |
| Silent embedding drift | RAG quality degrades without user knowing | Periodic retrieval quality report, re-index prompt |

---

## "Looks Done But Isn't" Checklist

- [ ] **Local LLM:** API endpoint saved but never validated on first use — verify connection succeeds
- [ ] **Local LLM:** Timeout set but doesn't distinguish first-token vs full-generation — verify long responses work
- [ ] **RAG:** Documents uploaded but not verifying embed success — check vector DB after upload
- [ ] **RAG:** Chunking implemented but no semantic boundary preservation — test with code/legal documents
- [ ] **Screenshots:** Capture working but no retention policy — verify old screenshots deleted
- [ ] **Screenshots:** Analysis running but no confidence threshold — tune threshold before shipping
- [ ] **Priority Queue:** Queue exists but starvation not tested — run 1000 priority items, verify normal still processes
- [ ] **Priority Queue:** High/low priority defined but no aging — check low-priority wait times after sustained load

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Hardcoded timeout failure | LOW | Update config, reconnect |
| Embedding drift | HIGH | Trigger re-indexing, notify user of brief unavailability |
| Screenshot storage full | MEDIUM | Auto-cleanup, show recovery UI |
| Priority starvation | LOW | Process queued normal items immediately, adjust algorithm |
| Priority inversion deadlock | MEDIUM | Kill stuck threads, reset queue, implement priority inheritance |
| Blocking screenshot analysis | LOW | Refactor to async, user sees brief pause |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Hardcoded timeout | LLM-03 | Test with slow/cold local model |
| OpenAI-compatible assumption | LLM-03 | Test each provider's streaming and function calls |
| Naive chunking | RAG-02 | Evaluate retrieval on code and legal documents |
| Embedding drift | RAG-02 | Simulate model update, verify re-index strategy works |
| Screenshot storage bloat | SCRN-02 | Run 8-hour session, verify disk usage bounded |
| False positive detection | SCRN-03 | Test with varied UI states, measure false positive rate |
| Priority starvation | PRIO-03 | Load test with sustained priority traffic |
| Priority inversion | PRIO-03 | Stress test with concurrent high/low priority processing |
| Screenshot blocks audio | SCRN-03 | Profile audio latency during screenshot analysis |
| Out-of-context retrieval | RAG-03 | Run retrieval evals with domain-specific questions |

---

## Sources

- [LLM API Timeout Issues](https://theeldersscripts.com/why-llm-api-calls-break-in-production/) — Elder Scripts, Nov 2025
- [Ollama OpenAI Compatibility](https://docs.ollama.com/api/openai-compatibility) — Ollama documentation
- [RAG Chunking Mistakes](https://python.plainenglish.io/why-70-of-rag-implementations-fail-and-the-6-things-that-separate-production-grade-systems-97501c11b682) — Python in Plain English, Dec 2025
- [Embedding Drift](https://www.reddit.com/r/LLMDevs/comments/1pefpzp/embedding_drift_actually_stabilized_our_rag/) — Reddit r/LLMDevs, Dec 2025
- [Priority Inversion in LangChain Agents](https://medium.com/@Modexa/priority-queues-that-make-langchain-agents-feel-fair-d0c6651eac70) — Medium, 2025
- [Python Concurrency Handbook](https://futurium.ec.europa.eu/en/apply-ai-alliance/community-content/introducing-python-concurrency-handbook-building-reliable-ai-europes-digital-future) — EU Futurium, Oct 2025

---
*Pitfalls research for: Local LLM API, RAG, Screenshot Automation, Priority Queues*
*Researched: 2026-04-14*
