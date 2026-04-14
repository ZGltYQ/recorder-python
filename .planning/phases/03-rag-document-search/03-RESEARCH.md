# Phase 3: RAG Document Search - Research

**Researched:** 2026-04-14
**Phase:** 03 - RAG Document Search
**Purpose:** Technical investigation for implementation planning

---

## Domain Overview

Phase 3 implements a RAG (Retrieval-Augmented Generation) system for document-based question answering. Users upload documents, they are chunked and embedded, stored in ChromaDB, and when a question is detected, relevant context is retrieved and included in the AI prompt.

**Key components:**
1. Document upload (file picker + drag-drop)
2. Document parsing and chunking (750 chars, 15% overlap)
3. Embedding generation (sentence-transformers, all-MiniLM-L6-v2)
4. ChromaDB storage with metadata
5. Vector similarity search (top-k retrieval)
6. Context injection into AI prompts
7. Citation display in UI

---

## 1. ChromaDB + Python Integration

### ChromaDB Client Setup

ChromaDB runs as an in-process database (embedded mode) by default, which is suitable for desktop apps. No server process needed.

```python
import chromadb
from chromadb.config import Settings

# Persistent storage in app data directory
client = chromadb.PersistentClient(
    path=str(app_data_dir / "chromadb"),
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)
```

### Collection Management

```python
# Create collection with embedding function
collection = client.get_or_create_collection(
    name="documents",
    metadata={"description": "RAG document chunks"},
    embedding_function=sentence_transformers_embedding_function  # Optional
)

# Add documents with pre-computed embeddings
collection.add(
    ids=[chunk_id],
    embeddings=[embedding_vector],  # List of floats, dim=384 for all-MiniLM-L6-v2
    documents=[chunk_text],
    metadatas=[{"source": filename, "chunk_index": i}]
)

# Query collection
results = collection.query(
    query_texts=[search_query],
    n_results=5,
    include=["documents", "metadatas", "distances"]
)
```

### Key Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Client type | PersistentClient | Desktop app, need persistence across sessions |
| Storage path | `~/.config/recorder-python/chromadb/` | Follows app config dir convention |
| Embedding function | Pre-compute + store | all-MiniLM-L6-v2 is deterministic, compute once |
| Collection naming | Single `documents` collection | Simple, manageable for single-user app |

### Thread Safety

ChromaDB's PersistentClient is **not thread-safe**. All operations must happen on the main thread or be serialized through Qt's event loop. Use Qt signals/slots to communicate between threads.

**Pattern:** ChromaDB operations run on main thread (or via QMetaObject::invokeMethod). QThread workers send signals to trigger operations.

---

## 2. sentence-transformers Embedding Workflows

### Model Loading

```python
from sentence_transformers import SentenceTransformer

# Load once, reuse
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
# Output dimension: 384

# Encode sentences
embeddings = model.encode(
    ["sentence 1", "sentence 2"],
    show_progress_bar=True,
    batch_size=32,
    convert_to_numpy=True  # For ChromaDB compatibility
)
```

### Async Pattern for PySide6

sentence-transformers is CPU/GPU bound. For non-blocking UI:

**Option A: QThread with signals (preferred for PySide6)**
```python
class EmbeddingWorker(QThread):
    progress = Signal(int, int)  # current, total
    complete = Signal(list)  # embeddings
    error = Signal(str)
    
    def __init__(self, texts: List[str]):
        super().__init__()
        self.texts = texts
        self.model = None
    
    def run(self):
        try:
            self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            embeddings = self.model.encode(
                self.texts,
                show_progress_bar=False,
                batch_size=32,
                convert_to_numpy=True,
                progress_handler=self._progress_hook
            )
            self.complete.emit(embeddings.tolist())
        except Exception as e:
            self.error.emit(str(e))
    
    def _progress_hook(self, batch, total):
        self.progress.emit(batch, total)
```

**Option B: asyncio with ThreadPoolExecutor**
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=1)

async def encode_async(texts):
    loop = asyncio.get_event_loop()
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    
    def encode():
        return model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    
    embeddings = await loop.run_in_executor(executor, encode)
    return embeddings.tolist()
```

### Progress Reporting

For indexing progress (D-05 requires progress indicator):
- sentence-transformers `encode()` accepts a `progress_handler` callback
- Emit Qt signals from worker thread
- Main window connects to progress signal, updates QProgressBar

---

## 3. Document Parsing

### TXT Files

Straightforward - read raw text with encoding detection:

```python
def parse_txt(filepath: Path) -> str:
    # Try UTF-8 first, fallback to latin-1
    try:
        return filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return filepath.read_text(encoding="latin-1")
```

### PDF Handling (Future - RAG-08)

For Phase 3, only TXT files. PDF would require:
- `PyPDF2` or `pdfplumber` for text extraction
- Note: RAG-08, RAG-09, RAG-10 are deferred to v2

### Chunking Strategy (D-02)

**750 characters with 15% overlap (~112 chars):**

```python
def chunk_text(text: str, chunk_size: int = 750, overlap: float = 0.15) -> List[Dict]:
    """Split text into overlapping chunks."""
    chunks = []
    overlap_chars = int(chunk_size * overlap)  # 112 chars
    
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Don't create tiny final chunks
        if len(chunk) < chunk_size * 0.5 and chunks:
            # Merge with previous chunk
            chunks[-1]["text"] += chunk
            chunks[-1]["end"] = start + len(chunk)
            break
        
        chunks.append({
            "text": chunk,
            "start": start,
            "end": end
        })
        
        start = end - overlap_chars  # Slide with overlap
    
    return chunks
```

**Metadata per chunk:**
```python
{
    "source": "document.txt",      # Filename
    "chunk_index": 0,              # Position in document
    "total_chunks": 5,            # For reference
    "upload_timestamp": "..."      # For retention decisions
}
```

---

## 4. RAG + Local LLM Integration

### Prompt Construction

When a question is detected, retrieve relevant chunks and inject into prompt:

```python
def build_rag_prompt(question: str, retrieved_chunks: List[Dict]) -> str:
    """Build prompt with retrieved context."""
    context_parts = []
    for chunk in retrieved_chunks:
        source = chunk["metadata"]["source"]
        context_parts.append(f"[Source: {source}]\n{chunk['text']}")
    
    context = "\n\n".join(context_parts)
    
    return f"""You are a helpful assistant. Use the following context to answer the question.

Context:
{context}

Question: {question}

Answer based on the context above. If the context doesn't contain relevant information, say so."""
```

### Citation Formatting (D-03)

**Inline badge format: 📄 DocumentName.txt**

When displaying AI answer with citations:
```python
def format_citation(filename: str) -> str:
    return f"📄 {filename}"

# Example output:
# "The meeting is scheduled for 3pm. 📄 notes.txt"
```

### Integration with AISuggestionGenerator

Existing `AISuggestionGenerator.generate_response()` in `openrouter.py` accepts `context` parameter:

```python
# Current signature:
async def generate_response(
    self, 
    question: str, 
    context: Optional[List[Dict[str, str]]] = None  # List of {text, source} dicts
) -> Optional[str]
```

RAG integration: Pass retrieved chunks as `context` list with `text` (chunk content) and `source` (filename) keys.

---

## 5. ChromaDB + PySide6 Architecture

### Recommended Module Structure

```
src/
└── rag/
        __init__.py
        manager.py       # ChromaDB client singleton, collection ops
        chunker.py       # Text chunking logic
        embedding.py     # EmbeddingWorker (QThread)
        search.py        # Query execution
```

### Pattern: QObject Signal/Slot for ChromaDB

```python
class RAGManager(QObject):
    """RAG operations manager with Qt signals."""
    
    indexing_progress = Signal(int, int)  # current, total chunks
    indexing_complete = Signal(str)  # document_id
    search_results = Signal(list)  # List[Dict] with chunks
    error = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._client = None
        self._collection = None
    
    def initialize(self):
        """Initialize ChromaDB client and collection."""
        # ChromaDB init on main thread
        self._client = chromadb.PersistentClient(
            path=str(get_config().get_data_dir() / "chromadb"),
            settings=Settings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            name="documents",
            metadata={"description": "RAG document chunks"}
        )
    
    @Slot(str, list)  # document_id, chunks
    def index_document(self, document_id: str, chunks: List[Dict]):
        """Index document chunks (called from embedding worker on complete)."""
        try:
            self._collection.add(
                ids=[f"{document_id}_{i}" for i in range(len(chunks))],
                embeddings=[c["embedding"] for c in chunks],
                documents=[c["text"] for c in chunks],
                metadatas=[c["metadata"] for c in chunks]
            )
            self.indexing_complete.emit(document_id)
        except Exception as e:
            self.error.emit(str(e))
    
    @Slot(str, int)
    def search(self, query: str, top_k: int = 5):
        """Search for relevant chunks."""
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            self.search_results.emit(self._format_results(results))
        except Exception as e:
            self.error.emit(str(e))
```

---

## 6. Document Upload UI

### Drag-Drop Zone (PySide6)

```python
class DocumentDropZone(QFrame):
    """Drop zone for document upload."""
    
    document_dropped = Signal(str)  # filepath
    
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumSize(300, 200)
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {COLORS["border"]};
                border-radius: 8px;
                background-color: {COLORS["surface"]};
            }}
            QFrame:hover {{
                border-color: {COLORS["primary"]};
            }}
        """)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            if filepath.endswith('.txt'):
                self.document_dropped.emit(filepath)
```

### Document List Display

Following existing `QListWidget` pattern from MainWindow (for sessions):
```python
class DocumentListWidget(QListWidget):
    """List of uploaded documents."""
    
    delete_requested = Signal(str)  # document_id
    
    def __init__(self):
        super().__init__()
        self.setSpacing(4)
    
    def add_document(self, doc_info: Dict):
        item = QListWidgetItem(f"📄 {doc_info['filename']}")
        item.setData(Qt.UserRole, doc_info['id'])
        self.addItem(item)
```

---

## 7. Validation Architecture

### Dimension 8: Testability

**Challenge:** RAG involves ML models (sentence-transformers, ChromaDB) making unit testing difficult.

**Mitigation:**
- ChromaDB operations are deterministic given same inputs
- Embedding model (all-MiniLM-L6-v2) produces consistent outputs
- Test chunking logic independently with known text inputs
- Test prompt construction with mocked retrieved chunks

### Key Verification Points

1. **Chunking:** Verify chunk size ~750 chars, overlap ~112 chars
2. **Embedding:** Verify dimension = 384 for all-MiniLM-L6-v2
3. **ChromaDB add:** Verify document appears in collection
4. **ChromaDB query:** Verify top-k results returned sorted by distance
5. **Citation format:** Verify "📄 filename.txt" pattern in output
6. **UI signals:** Verify progress bar updates during indexing

---

## 8. Dependencies to Add

```txt
# requirements.txt additions for Phase 3
chromadb>=0.4.22           # Vector database
sentence-transformers>=2.2.0  # Embeddings
```

---

## 9. Key Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| ChromaDB thread safety | All ops on main thread via Qt signals |
| Large document blocking UI | QThread worker with progress signals |
| Embedding model loading slow | Load once, cache in RAGManager singleton |
| No relevant documents found | Return empty results gracefully, AI says "no context" |
| ChromaDB corruption | `allow_reset=True` allows recovery, consider backup |

---

## 10. Implementation Sequence

1. **RAGManager** — ChromaDB client singleton, collection management
2. **DocumentChunker** — TXT parsing, chunking logic
3. **EmbeddingWorker** — QThread for sentence-transformers
4. **DocumentIndexingFlow** — Upload → parse → chunk → embed → store
5. **RAGSearchFlow** — Query → embed → ChromaDB → return chunks
6. **UIAugmentation** — Drop zone, document list, citation display
7. **Integration** — Connect to question detection and AI answering

---

## 11. Existing Codebase Reuse

| Pattern | Source | Reuse in Phase 3 |
|---------|--------|------------------|
| QThread worker | `src/speech/asr.py` (ASRWorker) | EmbeddingWorker follows same pattern |
| Qt signals | `TranscriptionManager` | RAGManager emits same signals |
| QObject + signals | `AudioCapture` | RAGManager inherits QObject |
| Dataclass | `TranscriptionResult` | DocumentChunk, SearchResult dataclasses |
| Config dir | `get_config().get_data_dir()` | ChromaDB storage path |
| Logger | `get_logger(__name__)` | All modules use same pattern |

---

## Summary

Phase 3 is technically feasible with well-established libraries:
- **ChromaDB** for vector storage (persistent, in-process)
- **sentence-transformers** for embeddings (all-MiniLM-L6-v2, 384 dim)
- **Qt patterns** already established in codebase for async work

**Main technical challenges:**
1. ChromaDB must run on main thread (Qt signal/slot bridge)
2. Embedding computation needs QThread worker with progress reporting
3. Integration with existing AISuggestionGenerator context injection

**Recommended approach:** Incremental implementation following the sequence in §10, with each component tested via its Qt signals before integration.

---

*Research complete. Next: Planning phase.*
