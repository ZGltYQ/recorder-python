# Roadmap: recorder-python

## Overview

Build AI-powered desktop recorder with local LLM support, RAG document search, screenshot automation, and priority queue for question answering. Phases follow dependency order: priority queue first (foundation for all AI features), then local LLM client (used by RAG and screenshots), then RAG module, then screenshot mode.

## Phases

- [ ] **Phase 1: Priority Queue Foundation** - Priority queue system for question answering with starvation prevention
- [ ] **Phase 2: Local LLM Client** - Custom LLM API endpoint configuration and provider selection
- [ ] **Phase 3: RAG Document Search** - Document upload, embedding, and context-augmented AI answers
- [ ] **Phase 4: Screenshot Mode** - Interval screenshot capture with AI task detection and auto-solve

## Phase Details

### Phase 1: Priority Queue Foundation
**Goal**: Users can prioritize question answering with keyword-detected questions answered before AI-detected questions
**Depends on**: Nothing (first phase)
**Requirements**: PRIO-01, PRIO-02, PRIO-03, PRIO-04
**Success Criteria** (what must be TRUE):
  1. Keyword-detected questions enter priority answer queue (fast path)
  2. Background AI-detected questions enter normal queue
  3. Priority queue answered before normal queue with starvation prevention via aging
  4. Queue depth (priority vs normal count) displayed in UI
**Plans**: 2 plans
Plans:
- [x] 01-01-PLAN.md — PriorityQueueManager with asyncio.PriorityQueue and Qt signals
- [x] 01-02-PLAN.md — Gap closure: Fix QueuedQuestion comparison operators and implement aging

### Phase 2: Local LLM Client
**Goal**: Users can configure and use custom local LLM API endpoints alongside OpenRouter
**Depends on**: Phase 1
**Requirements**: LLM-01, LLM-02, LLM-03, LLM-04
**Success Criteria** (what must be TRUE):
  1. User can configure custom LLM API endpoint (base URL, model name, optional API key)
  2. User can select which LLM provider to use per conversation (OpenRouter or Local)
  3. App calls local LLM API with OpenAI-compatible chat completions format
  4. Local LLM timeout is configurable (minimum 300s for cold-start models)
**Plans**: 2 plans
Plans:
- [ ] 02-01-PLAN.md — LocalLLMClient and provider integration
- [ ] 02-02-PLAN.md — Settings dialog Local LLM UI and provider selector

### Phase 3: RAG Document Search
**Goal**: Users can upload documents and receive context-augmented AI answers with citations
**Depends on**: Phase 2
**Requirements**: RAG-01, RAG-02, RAG-03, RAG-04, RAG-05, RAG-06, RAG-07
**Success Criteria** (what must be TRUE):
  1. User can upload TXT documents via file picker or drag-drop
  2. Uploaded documents are parsed, chunked (500-1000 chars with overlap), and stored
  3. Document chunks are embedded with sentence-transformers and stored in ChromaDB with source metadata
  4. When question is detected, app searches document knowledge base (top-k retrieval)
  5. Relevant document context is included in AI prompt for answering
  6. Answers sourced from documents show inline citation ("Answer from: DocumentName.pdf")
**Plans**: TBD
**UI hint**: yes

### Phase 4: Screenshot Mode
**Goal**: Users can enable interval-based screenshot capture with AI task detection and auto-solve
**Depends on**: Phase 3
**Requirements**: SCRN-01, SCRN-02, SCRN-03, SCRN-04, SCRN-05, SCRN-06
**Success Criteria** (what must be TRUE):
  1. User can enable screenshot mode with configurable interval (5-300 seconds, default 30s)
  2. App captures screenshot at configured interval (runs in QThread, never blocks audio pipeline)
  3. Screenshots are analyzed by AI for actionable tasks
  4. Detected tasks are auto-solved by AI
  5. Task solutions displayed in side panel with explanation
  6. Screenshot storage has retention policy (circular buffer, configurable max count)
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Priority Queue Foundation | 2/2 | Ready to execute | - |
| 2. Local LLM Client | 0/2 | Ready to plan | - |
| 3. RAG Document Search | 0/7 | Not started | - |
| 4. Screenshot Mode | 0/6 | Not started | - |
