# Architecture Research

**Domain:** PySide6 Desktop Application with AI Integration
**Researched:** 2026-04-14
**Confidence:** HIGH

## Executive Summary

The existing recorder-python application uses a Qt signal/slot event-driven architecture. New features (Local LLM API, RAG, Screenshot mode, Priority queue) integrate naturally into this paradigm by extending the AI layer with new components that emit Qt signals for async results. The key architectural decision is that **Local LLM uses a factory pattern** to select between OpenRouter and local endpoints, **RAG becomes a retrieval service** within the AI layer, **Screenshot capture runs in its own QThread** to avoid blocking recording, and **Priority queue uses asyncio.PriorityQueue** integrated with the existing event loop.

## Integration with Existing Architecture

### Current Layer Structure (from existing ARCHITECTURE.md)

```
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer (GUI)                        │
├─────────────────────────────────────────────────────────────┤
│  MainWindow ←→ SettingsDialog ←→ SidePanel                 │
└─────────────────────────────┬───────────────────────────────┘
                              │ Qt signals/slots
┌─────────────────────────────↓───────────────────────────────┐
│                    Audio/Speech Layer                       │
│  AudioCapture ←→ Qwen3ASR ←→ SpeakerDiarization           │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────↓───────────────────────────────┐
│                       AI Layer                               │
│  OpenRouterClient, QuestionDetector, AISuggestionGenerator  │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────↓───────────────────────────────┐
│                     Data Layer                               │
│  DatabaseManager, ConfigManager                             │
└─────────────────────────────────────────────────────────────┘
```

### Extended Architecture with New Components

```
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer (GUI)                        │
├─────────────────────────────────────────────────────────────┤
│  MainWindow ←→ SettingsDialog ←→ SidePanel                 │
└─────────────────────────────┬───────────────────────────────┘
                              │ Qt signals/slots
┌─────────────────────────────↓───────────────────────────────┐
│                    Audio/Speech Layer                        │
│  AudioCapture ←→ Qwen3ASR ←→ SpeakerDiarization           │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────↓───────────────────────────────┐
│                       AI Layer (EXTENDED)                   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────────────────────────┐  │
│  │ LLMClientFactory │  │ PriorityAnswerQueue (asyncio)  │  │
│  │  ├──OpenRouter  │  │  ├── PRIORITY_HIGH (keyword)    │  │
│  │  └──LocalLLM    │  │  └── PRIORITY_NORMAL (AI-detect)│  │
│  └────────┬────────┘  └──────────────────────────────────┘  │
│           │                                                  │
│  ┌────────┴────────┐  ┌────────────┐  ┌─────────────────┐  │
│  │RAGRetriever     │  │Screenshot  │  │QuestionDetector │  │
│  │ (document store │  │Analyzer    │  │(enhanced)       │  │
│  │  + embedder)    │  │(QThread)   │  │                 │  │
│  └─────────────────┘  └────────────┘  └─────────────────┘  │
│           │                  │                   │          │
│  ┌────────┴──────────────────┴───────────────────┴────────┐ │
│  │              AISuggestionGenerator (unchanged)          │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────↓───────────────────────────────┐
│                     Data Layer (EXTENDED)                   │
│  DatabaseManager  ConfigManager  DocumentStore (filesystem) │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | Location | Pattern |
|-----------|----------------|----------|---------|
| `LLMClientFactory` | Creates LLM client based on provider selection (OpenRouter/Local) | `src/ai/llm_factory.py` | Factory pattern |
| `LocalLLMClient` | Calls local LLM API with OpenAI-compatible interface | `src/ai/local_llm.py` | Extends base client |
| `RAGRetriever` | Stores documents, generates embeddings, retrieves context | `src/rag/` | New module |
| `DocumentStore` | Manages document files on filesystem | `src/rag/store.py` | File-based |
| `Embedder` | Generates embeddings for document chunks | `src/rag/embedder.py` | Uses sentence-transformers |
| `ScreenshotCapture` | Captures screenshots on interval in QThread | `src/screenshot/capture.py` | QThread worker |
| `ScreenshotAnalyzer` | Analyzes screenshots for actionable tasks via LLM | `src/screenshot/analyzer.py` | Async |
| `PriorityAnswerQueue` | Manages priority queue for AI response requests | `src/ai/priority_queue.py` | asyncio.PriorityQueue |

## Recommended Project Structure

```
src/
├── ai/                          # Existing AI layer (extend)
│   ├── __init__.py
│   ├── openrouter.py            # Existing - do not modify interface
│   ├── llm_factory.py           # NEW - LLMClientFactory
│   ├── local_llm.py             # NEW - LocalLLMClient  
│   ├── priority_queue.py        # NEW - PriorityAnswerQueue
│   └── question_detector.py     # Existing - enhanced
├── rag/                         # NEW - RAG module
│   ├── __init__.py
│   ├── store.py                 # Document storage
│   ├── chunker.py               # Document chunking
│   ├── embedder.py              # Embedding generation
│   └── retriever.py             # Similarity retrieval
├── screenshot/                  # NEW - Screenshot module
│   ├── __init__.py
│   ├── capture.py               # QThread screenshot capture
│   └── analyzer.py              # Screenshot analysis
├── audio/                       # Existing - unchanged
│   └── ...
├── speech/                      # Existing - unchanged
│   └── ...
├── database/                    # Existing - unchanged
│   └── ...
├── gui/                        # Existing - unchanged
│   └── ...
└── utils/                      # Existing - unchanged
    └── ...
```

## Architectural Patterns

### Pattern 1: LLM Factory (Strategy/Factory)

**What:** Factory pattern for creating LLM client based on provider selection.

**When to use:** When multiple implementations share the same interface but differ in configuration.

**Trade-offs:**
- PRO: Clean separation of provider-specific logic
- PRO: Easy to add new providers
- CON: Slight indirection

**Example:**
```python
# src/ai/llm_factory.py
from abc import ABC, abstractmethod

class LLMClientBase(ABC):
    @abstractmethod
    async def chat(self, messages: List[Message]) -> ChatResponse:
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        pass

class OpenRouterClient(LLMClientBase):
    # Existing implementation from openrouter.py
    pass

class LocalLLMClient(LLMClientBase):
    # NEW - similar interface, different base URL
    BASE_URL = None  # Set via constructor
    
    def __init__(self, endpoint_url: str, model: str):
        self.endpoint_url = endpoint_url
        self.model = model
        # No auth header needed for local

class LLMClientFactory:
    @staticmethod
    def create(provider: str, **kwargs) -> LLMClientBase:
        if provider == "openrouter":
            return OpenRouterClient(**kwargs)
        elif provider == "local":
            return LocalLLMClient(**kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider}")
```

### Pattern 2: Priority Queue (asyncio.PriorityQueue)

**What:** Priority queue using asyncio for managing AI response requests with keyword-detected questions processed first.

**When to use:** When you need to handle requests with different priority levels asynchronously.

**Trade-offs:**
- PRO: Natural priority handling
- PRO: Async-native, integrates with existing httpx usage
- PRO: Built-in thread safety
- CON: Requires async/await throughout pipeline

**Example:**
```python
# src/ai/priority_queue.py
import asyncio
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional, Callable

class Priority(IntEnum):
    HIGH = 0   # Keyword-detected question
    NORMAL = 1 # AI-detected question

@dataclass
class AnswerRequest:
    priority: Priority
    question: str
    context: Optional[List[Dict]] = None
    callback: Optional[Callable] = None

class PriorityAnswerQueue:
    def __init__(self):
        self._queue = asyncio.PriorityQueue()
        self._workers = []
        
    async def enqueue(self, request: AnswerRequest):
        await self._queue.put((request.priority.value, request))
        
    async def process(self, llm_client: LLMClientBase):
        while True:
            _, request = await self._queue.get()
            response = await llm_client.chat(...)
            if request.callback:
                request.callback(response)
            self._queue.task_done()
```

### Pattern 3: Screenshot Capture Thread (QThread Worker)

**What:** QThread-based screenshot capture that emits signals with captured images, decoupled from analysis.

**When to use:** When you need periodic background work that must not block the main Qt event loop.

**Trade-offs:**
- PRO: Native Qt threading pattern
- PRO: Signals provide clean thread-safe GUI updates
- PRO: Capture continues independently of analysis
- CON: Slightly complex signal/slot wiring

**Example:**
```python
# src/screenshot/capture.py
from PySide6.QtCore import QThread, Signal, QTimer

class ScreenshotCapture(QThread):
    screenshot_ready = Signal(object)  # Emits QPixmap or file path
    
    def __init__(self, interval_seconds: int = 30):
        super().__init__()
        self.interval = interval_seconds
        self._stop_event = threading.Event()
        
    def run(self):
        while not self._stop_event.is_set():
            pixmap = QGuiApplication.primaryScreen().grabWindow(0)
            self.screenshot_ready.emit(pixmap)
            self._stop_event.wait(self.interval)
            
    def stop(self):
        self._stop_event.set()
        self.wait()

class ScreenshotAnalyzer:
    """Async analyzer - runs in main thread via Qt event loop"""
    
    def __init__(self, llm_client: LLMClientBase):
        self.llm = llm_client
        
    async def analyze(self, pixmap):
        # Convert to base64, send to LLM
        # Emit results via signal
        pass
```

### Pattern 4: RAG Retrieval Service

**What:** Document storage + embedding + retrieval as a service layer that augment LLM prompts.

**When to use:** When you need to provide contextual documents to LLM for answering domain-specific questions.

**Trade-offs:**
- PRO: Clean separation of concerns
- PRO: Can swap embedding models
- PRO: Documents stored locally (privacy)
- CON: Embedding generation adds latency

**Example:**
```python
# src/rag/retriever.py
class RAGRetriever:
    def __init__(self, embedder: Embedder, store: DocumentStore):
        self.embedder = embedder
        self.store = store
        
    async def retrieve_context(self, query: str, top_k: int = 5) -> List[str]:
        query_embedding = await self.embedder.embed(query)
        chunks = await self.store.similarity_search(query_embedding, top_k)
        return [chunk.text for chunk in chunks]
        
    def augment_prompt(self, question: str, context: List[str]) -> List[Message]:
        context_text = "\n\n".join(context)
        return [
            Message(role="system", content="Use the following context to answer..."),
            Message(role="user", content=f"Context:\n{context_text}\n\nQuestion: {question}")
        ]
```

## Data Flow

### Question Answering Flow (with Priority + RAG)

```
[Audio] → [Transcription] → [QuestionDetector.is_question()]
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
              [Keyword match?]                [AI-detected?]
                    │                               │
                    ↓                               ↓
            [PRIORITY_HIGH]               [PRIORITY_NORMAL]
            [enqueue with                          [enqueue with
             priority=0]                           priority=1]
                    │                               │
                    └───────────────┬───────────────┘
                                    ↓
                        [PriorityAnswerQueue]
                                    │
                                    ↓ (worker picks next HIGH before NORMAL)
                        [RAGRetriever.retrieve_context()]
                                    │
                                    ↓
                        [LLMClientFactory.create(provider).chat()]
                                    │
                                    ↓
                        [response via callback/signal]
                                    │
                                    ↓
                            [SidePanel display]
```

### Screenshot Flow

```
[User enables screenshot mode]
           │
           ↓
[ScreenshotCapture.start(interval=30s)]
           │
           ├─→ [Timer fires every 30s in QThread]
           │          │
           │          ↓
           │    [grabWindow() capture]
           │          │
           │          ↓
           │    [screenshot_ready signal]
           │          │
           │          ↓
           ├─→ [MainWindow.on_screenshot()]
           │          │
           │          ↓
           │    [ScreenshotAnalyzer.analyze()]
           │          │
           │          ↓
           │    [LLM detects actionable task?]
           │          │
           │    ┌─────┴─────┐
           │    │           │
           │   YES         NO
           │    │           │
           │    ↓           ↓
           │ [TaskSolver]  [discard]
           │    │
           │    ↓
           │ [task_ready signal]
           │    │
           │    ↓
           └─→ [SidePanel displays task + solution]
```

### RAG Document Upload Flow

```
[User uploads document (PDF, TXT, etc.)]
           │
           ↓
[DocumentStore.store(file)]
           │
           ↓
[Chunker.chunk(document)]
           │
           ↓
[Embedder.embed(chunks)]
           │
           ↓
[DocumentStore.index(chunks_with_embeddings)]
           │
           ↓
[Document ready for retrieval]
```

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Local LLM API | httpx POST to `/v1/chat/completions` | OpenAI-compatible; endpoint URL + model name from config |
| OpenRouter API | Existing `OpenRouterClient` | Unchanged; add provider selection per conversation |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Audio → AI Layer | Qt signal `transcription_ready` | Existing; AI layer receives text |
| AI Layer → RAG | Direct method call | `rag_retriever.retrieve_context()` |
| Screenshot → Analyzer | Qt signal `screenshot_ready` | Pixmap passed through signal |
| PriorityQueue → LLM | Async method call | `llm.chat()` |
| AI Layer → GUI | Qt signal `ai_response_ready` | Existing pattern |

### Config Integration

```python
# New config fields in OpenRouterConfig or new dataclass
@dataclass
class LocalLLMConfig:
    enabled: bool = False
    endpoint_url: str = "http://localhost:11434/v1/chat/completions"  # Ollama default
    model: str = "llama3"
    
@dataclass  
class RAGConfig:
    enabled: bool = True
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 500
    top_k: int = 5

@dataclass
class ScreenshotConfig:
    enabled: bool = False
    interval_seconds: int = 30
    auto_solve: bool = True
```

## Build Order Implications

### Phase 1: Priority Queue (Foundation)
- **Why first:** Other features (Local LLM, RAG) all submit AI requests
- **Dependencies:** None (pure asyncio, no new external dependencies)
- **Changes:** Add `src/ai/priority_queue.py`

### Phase 2: Local LLM Client
- **Why second:** Uses priority queue for request handling
- **Dependencies:** Priority queue
- **Changes:** Add `src/ai/local_llm.py`, `src/ai/llm_factory.py`
- **Config:** Add `LocalLLMConfig`

### Phase 3: RAG Module
- **Why third:** Depends on LLM client for prompt augmentation
- **Dependencies:** LLM factory (to call API), embedding model
- **Changes:** Add `src/rag/` entire module
- **Config:** Add `RAGConfig`

### Phase 4: Screenshot Mode
- **Why fourth:** Uses LLM client for analysis
- **Dependencies:** LLM factory, priority queue
- **Changes:** Add `src/screenshot/` module
- **Config:** Add `ScreenshotConfig`

## Anti-Patterns

### Anti-Pattern 1: Blocking LLM Calls in Audio Thread

**What people do:** Making synchronous LLM API calls when processing audio chunks.

**Why it's wrong:** Audio capture is time-sensitive; blocking causes dropped frames, choppy recording.

**Do this instead:** Always use async LLM calls via `asyncio.create_task()` or priority queue. Audio thread never waits for AI response.

### Anti-Pattern 2: Embedding at Query Time

**What people do:** Generating embeddings for the query without caching document embeddings.

**Why it's wrong:** Embedding generation is slow; querying becomes sluggish.

**Do this instead:** Pre-compute and cache document embeddings at ingestion time. Query embedding is lightweight by comparison.

### Anti-Pattern 3: Single Priority Queue Instance with Blocking Dequeue

**What people do:** Using a single priority queue but blocking on `get()` which prevents higher-priority items from being processed.

**Why it's wrong:** If normal-priority items are being processed, high-priority items must wait even when the queue could prioritize.

**Do this instead:** Use `asyncio.PriorityQueue` which returns items sorted by priority automatically. Workers should await `queue.get()` which correctly returns lowest-priority value first.

## Sources

- [Qt Screen Capture Documentation](https://doc.qt.io/qtforpython-6/examples/example_multimedia_screencapture.html) - Qt official
- [PySide6 Multithreading Best Practices](https://www.pythonguis.com/tutorials/multithreading-pyside6-applications-qthreadpool/) - Python GUIs
- [Ollama OpenAI Compatibility](https://ollama.com/blog/openai-compatibility) - Local LLM API standard
- [RAG Architecture Patterns](https://python.plainenglish.io/best-open-source-embedding-models-for-rag-your-2025-guide-feffe6b8bb68) - RAG best practices
- [asyncio Priority Queue](https://docs.python.org/3/library/asyncio-queue.html#asyncio.PriorityQueue) - Python stdlib

---
*Architecture research for: recorder-python desktop app extension*
*Researched: 2026-04-14*
