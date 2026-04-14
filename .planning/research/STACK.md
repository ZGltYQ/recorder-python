# Stack Research

**Domain:** Desktop Audio Recorder with LLM, RAG, and Screenshot Analysis
**Researched:** 2026-04-14
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| httpx | 0.27.0+ | Async HTTP client for LLM API calls | Built-in async/await, streaming support, same interface works for OpenRouter and local LLM endpoints. The existing codebase already uses httpx 0.25.0+. |
| sentence-transformers | 3.0.0+ | Text embeddings for RAG | High-quality open-source embeddings, all-MiniLM-L6-v2 is fast (384-dim, ~22M params) and effective for semantic search. Native async encode support via `encode_async()`. |
| ChromaDB | 0.5.0+ | Local vector database | Local-first, zero-config, Python-native API. Persistent storage by default. Integrates cleanly with sentence-transformers. FAISS alternative if ChromaDB proves too heavy. |
| Docling | 2.0.0+ | Unified document parsing | IBM-backed, MIT-licensed. Parses PDF, DOCX, PPTX, XLSX, HTML, EPUB, ODT, RTF, images. Self-contained, no external service dependencies. Outperforms fragmented per-format solutions. |
| PySide6.QtMultimedia | (ships with PySide6 6.6.0+) | Screenshot capture | Qt's official screen capture API. `QScreenCapture` for full screenshots, `QWindowCapture` for window-specific capture. Integrated with Qt event loop—native fit for the existing PySide6 app. |
| asyncio.PriorityQueue | (stdlib) | Priority task queue | Built into Python stdlib. `asyncio.PriorityQueue` accepts `(priority, item)` tuples—lower int = higher priority. No external dependency. Works seamlessly with existing `async/await` patterns. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyMuPDF (pymupdf) | 1.25.0+ | PDF text/table extraction | Fallback for PDFs that Docling misrenders. Docling uses MuPDF under the hood anyway. |
| python-docx | 1.1.0+ | DOCX text extraction | When Docling output is insufficient for DOCX. Most reliable pure-Python DOCX parser. |
| markdown | 3.5+ | Markdown parsing | For extracting text from MD files directly. |
| ebooklib | 0.5+ | EPUB parsing | Lightweight EPUB extraction. Alternative: `pyepub`. |
| olefile | 0.47+ | RTF/ODT parsing | RTF and ODT are ZIP-based; olefile helps with embedded objects. For simple text extraction, raw ZIP handling often suffices. |
| PIL (Pillow) | 10.0+ | Image processing for screenshots | Resize, compress, convert screenshots before sending to LLM. Reduces token costs. |
| pydantic | 2.5+ | Data validation | Validate LLM API responses, document metadata, task queue items. Already in existing stack. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest + pytest-asyncio | Async test support | Existing stack. Use `@pytest.mark.asyncio` for async tests. |
| ruff | Linting | Existing stack. |

## Installation

```bash
# Core LLM/RAG
pip install httpx>=0.27.0

# Embeddings
pip install sentence-transformers>=3.0.0

# Vector storage
pip install chromadb>=0.5.0

# Document parsing (Docling + fallbacks)
pip install docling>=2.0.0
pip install pymupdf>=1.25.0
pip install python-docx>=1.1.0
pip install markdown>=3.5
pip install ebooklib>=0.5
pip install olefile>=0.47

# Image processing
pip install pillow>=10.0.0

# Already in existing stack: pydantic, structlog
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| ChromaDB | FAISS | If ChromaDB startup time or persistence complexity is problematic. FAISS is pure C++ with Python bindings, faster for large corpora, but requires manual index management. |
| Docling | PyMuPDF + per-format parsers | If Docling has bugs with a specific format you care about. Fragmented approach gives more control but more integration code. |
| sentence-transformers | OpenAI embeddings API | If privacy constraints are lifted. OpenAI's `text-embedding-3-small` is smaller (256-dim) and likely higher quality, but sends data externally. |
| asyncio.PriorityQueue | Celery + Redis | If you need distributed task processing across machines. Overkill for a desktop app. Redis adds operational complexity. |
| QScreenCapture | mss / Pillow screenshot | If QScreenCapture has platform issues (Wayland, macOS). mss is pure Python, faster, but requires separate integration with Qt event loop. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `requests` library | Sync-only, blocks event loop. Existing app uses `httpx` for async. | httpx with `AsyncClient` |
| `llama-index` or `langchain` for RAG | Heavy abstraction layers. Overkill for simple document ingestion + semantic search. You only need embeddings + vector store + manual prompt injection. | Direct sentence-transformers + ChromaDB |
| `pypdf` / `PyPDF2` | Slower than PyMuPDF, fewer features. PyMuPDF has better table extraction. | PyMuPDF (pymupdf) |
| `python-magic` | Requires libmagic system dependency. Platform-specific issues. | `pathlib` + extension-based format detection |
| `Celery` for desktop priority queue | Requires separate worker process, Redis broker. Designed for distributed systems. | `asyncio.PriorityQueue` |
| `aiohttp` as primary HTTP client | Already using httpx. httpx has cleaner API and supports both sync/async. | httpx |

## Stack Patterns by Variant

**If screenshot analysis is slow and causing token costs:**
- Use `Pillow` to resize screenshots before LLM analysis (e.g., 1280px max width)
- Consider sending thumbnails first, full image only if task detected

**If document corpus is large (>1000 pages):**
- Use FAISS instead of ChromaDB for faster similarity search
- Chunk documents intelligently (by heading, not fixed token counts)
- Consider embedding at paragraph level rather than page level

**If local LLM endpoint is Ollama:**
- Ollama exposes OpenRouter-compatible endpoint at `http://localhost:11434/v1/chat/completions`
- Same `httpx` code works with just a different base URL
- Consider `ollama-python` library for async streaming if available

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| httpx 0.27.0 | PySide6 6.6.0+ | Uses stdlib asyncio. No conflicts. |
| sentence-transformers 3.0.0 | torch 2.1.0+ | Already in stack. GPU support automatic. |
| ChromaDB 0.5.0 | Python 3.10+ | Already satisfied. |
| Docling 2.0.0 | PyMuPDF 1.25.0+ | Docling bundles MuPDF but uses system MuPDF if present. |
| PySide6 6.6.0+ | Qt6.5+ | QScreenCapture requires Qt Multimedia which is included in standard PySide6 installs. |

## Sources

- Context7 `/encode/httpx` — AsyncClient, streaming, POST patterns
- Context7 `/pymupdf/pymupdf` — PDF text extraction
- Context7 `/huggingface/sentence-transformers` — `encode()`, semantic search, `all-MiniLM-L6-v2`
- OpenRouter Docs (https://openrouter.ai/docs/quickstart) — API format verified, `POST /v1/chat/completions`, Bearer auth
- Qt for Python Docs (https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QScreenCapture.html) — QScreenCapture API
- WebSearch — Screenshot patterns, ChromaDB vs FAISS comparison, Docling as unified parser

---
*Stack research for: Local LLM API, RAG ingestion, Screenshot capture, Priority queue*
*Researched: 2026-04-14*
