# Phase 3: RAG Document Search - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 03-rag-document-search
**Areas discussed:** Document management, Chunking strategy, Citation display, RAG trigger strategy, Embeddings computation

---

## Area 1: Document Management

| Option | Description | Selected |
|--------|-------------|----------|
| Full CRUD | Users can upload, view, delete documents | ✓ |
| Upload only | Users can upload, view list, but cannot delete | |
| Upload with rename | Upload and rename, no delete | |

**User's choice:** Full CRUD
**Notes:** Users need to manage their document collection over time

---

## Area 2: Chunking Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| 500 chars / 10% overlap | Smaller chunks, higher recall | |
| 750 chars / 15% overlap | Balanced approach | ✓ |
| 1000 chars / 20% overlap | Larger chunks, better context | |

**User's choice:** 750 chars / 15% overlap
**Notes:** Good balance between semantic coherence and retrieval precision

---

## Area 3: Citation Display

| Option | Description | Selected |
|--------|-------------|----------|
| Footnote | Numbered footnote with document link at bottom | |
| Inline badge | 📄 DocumentName.txt inline with answer | ✓ |
| Tooltip | Hover tooltip showing source | |

**User's choice:** Inline badge (📄 DocumentName.txt)
**Notes:** Visually distinct but not intrusive; shows document icon + filename

---

## Area 4: RAG + Question Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Every question | Always search RAG when question detected | |
| Hybrid | Auto if docs uploaded + manual trigger option | ✓ |
| Manual only | Only when user explicitly searches | |

**User's choice:** Hybrid approach
**Notes:** Automatic when documents available, plus manual trigger for explicit retrieval

---

## Area 5: Embeddings Computation

| Option | Description | Selected |
|--------|-------------|----------|
| Sync (blocking) | Wait for indexing to complete | |
| Async with progress | Show progress indicator, non-blocking | ✓ |
| Async minimal | Background with no feedback | |

**User's choice:** Async with progress indicator
**Notes:** User can continue using app while indexing; shows progress bar

---

## the agent's Discretion

- Chunking overlap percentage can be fine-tuned during implementation
- Exact progress bar UI styling (position, colors) — follow app conventions
- ChromaDB collection naming and metadata schema

## Deferred Ideas

None
