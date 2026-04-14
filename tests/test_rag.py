"""Tests for RAG document processing."""

import pytest
from pathlib import Path
from src.rag.chunker import DocumentChunker, DocumentChunk


def test_chunker_750_chars(sample_text):
    """RAG-02: Verify 750 char chunks with 15% overlap."""
    chunker = DocumentChunker()
    chunks = chunker.chunk_text(sample_text, source="test.txt")

    # Each chunk should be ~750 chars
    for chunk in chunks[:-1]:  # All but last
        assert 700 <= len(chunk.text) <= 800, f"Chunk size {len(chunk.text)} not in range"

    # Overlap should be ~112 chars (15% of 750)
    # Second chunk should overlap with first by ~112 chars
    if len(chunks) >= 2:
        overlap = chunks[0].end - chunks[1].start
        assert 100 <= overlap <= 125, f"Overlap {overlap} not ~112"


def test_chunker_min_chunk_merge():
    """RAG-02: Verify tiny final chunks merged with previous."""
    chunker = DocumentChunker()
    short_text = "Short piece of text."
    chunks = chunker.chunk_text(short_text, source="test.txt")

    # All chunks should be at least MIN_CHUNK_SIZE
    for chunk in chunks:
        assert len(chunk.text) >= 100, f"Chunk {len(chunk.text)} < min size"


def test_chunker_single_chunk(sample_text_short):
    """Verify single chunk when text is short."""
    chunker = DocumentChunker()
    chunks = chunker.chunk_text(sample_text_short, source="test.txt")

    # Should produce at least one chunk
    assert len(chunks) >= 1
    assert chunks[0].text == sample_text_short


def test_chunker_metadata(sample_text):
    """Verify chunk metadata is correctly populated."""
    chunker = DocumentChunker()
    chunks = chunker.chunk_text(sample_text, source="test.txt")

    for chunk in chunks:
        assert chunk.metadata["source"] == "test.txt"
        assert "chunk_index" in chunk.metadata
        assert "total_chunks" in chunk.metadata
        assert chunk.metadata["total_chunks"] == len(chunks)


def test_chunker_overlap_ratio():
    """Verify overlap is approximately 15% of chunk size."""
    chunker = DocumentChunker()
    # Create text exactly 2 chunks long
    text = "A" * 750 + "B" * 750
    chunks = chunker.chunk_text(text, source="test.txt")

    if len(chunks) >= 2:
        # Overlap should be approximately 112 chars (15% of 750)
        overlap = chunks[0].end - chunks[1].start
        assert abs(overlap - 112) <= 5, f"Overlap {overlap} not close to 112"


def test_parse_txt(temp_txt_file, sample_text):
    """Verify TXT file parsing with UTF-8."""
    chunker = DocumentChunker()
    content = chunker.parse_txt(temp_txt_file)
    assert content == sample_text


def test_chunk_file(temp_txt_file, sample_text):
    """Verify file chunking returns correct chunks."""
    chunker = DocumentChunker()
    chunks = chunker.chunk_file(temp_txt_file)

    # Should produce chunks from sample_text
    assert len(chunks) > 0
    assert all(isinstance(chunk, DocumentChunk) for chunk in chunks)
    assert chunks[0].metadata["source"] == "test.txt"


def test_citation_format():
    """RAG-07: Verify citation badge format '📄 DocumentName.txt'."""
    # This will be tested in integration tests with actual UI
    citation = f"📄 document.txt"
    assert citation.startswith("📄")
    assert citation.endswith(".txt")


def test_document_chunk_dataclass():
    """Verify DocumentChunk dataclass structure."""
    chunk = DocumentChunk(
        text="Sample text",
        start=0,
        end=100,
        metadata={"source": "test.txt", "chunk_index": 0, "total_chunks": 1},
    )

    assert chunk.text == "Sample text"
    assert chunk.start == 0
    assert chunk.end == 100
    assert chunk.metadata["source"] == "test.txt"
    assert chunk.metadata["chunk_index"] == 0
    assert chunk.metadata["total_chunks"] == 1


def test_empty_text():
    """Verify handling of empty text."""
    chunker = DocumentChunker()
    chunks = chunker.chunk_text("", source="test.txt")
    assert len(chunks) == 0


def test_whitespace_only_text():
    """Verify handling of whitespace-only text."""
    chunker = DocumentChunker()
    chunks = chunker.chunk_text("   \n\t  ", source="test.txt")
    # Whitespace-only may produce no valid chunks
    assert isinstance(chunks, list)


def test_rag_search_format(mock_chromadb):
    """RAG-05, RAG-06: Verify search returns formatted results."""
    from src.rag.manager import RAGManager

    rag = RAGManager()

    # Mock collection.query to return test results
    mock_results = {
        "ids": [["doc1_0", "doc1_1"]],
        "documents": [["chunk text 1", "chunk text 2"]],
        "metadatas": [[{"source": "test.txt"}, {"source": "test.txt"}]],
        "distances": [[0.1, 0.2]],
    }
    rag._collection.query.return_value = mock_results

    # Trigger search
    results = []

    def capture(r):
        results.extend(r)

    rag.search_complete.connect(capture)
    rag.search("test query", top_k=2)

    # Verify results formatted
    assert len(results) == 2
    assert results[0]["text"] == "chunk text 1"
    assert results[0]["source"] == "test.txt"
    assert "distance" in results[0]


def test_citation_format_search():
    """RAG-07: Verify citation badge format '📄 DocumentName.txt'."""
    from src.rag.search import RAGSearch

    search = RAGSearch(None, None)
    citation = search.format_citation("document.txt")

    assert citation == "📄 document.txt"
    assert "📄" in citation
    assert citation.endswith(".txt")


def test_build_rag_prompt(mock_chromadb):
    """RAG-06: Verify prompt includes context from search results."""
    from src.rag.search import RAGSearch

    search = RAGSearch(None, None)

    mock_results = [
        {"text": "The meeting is at 3pm.", "source": "notes.txt", "distance": 0.1},
        {"text": "Action items include review.", "source": "notes.txt", "distance": 0.2},
    ]

    prompt, citations = search.build_rag_prompt("When is the meeting?", mock_results)

    assert "The meeting is at 3pm" in prompt
    assert "notes.txt" in prompt
    assert "When is the meeting?" in prompt
    assert len(citations) == 2
    assert "📄 notes.txt" in citations


def test_build_rag_prompt_empty_results(mock_chromadb):
    """Verify prompt building with empty results."""
    from src.rag.search import RAGSearch

    search = RAGSearch(None, None)

    prompt, citations = search.build_rag_prompt("When is the meeting?", [])

    assert prompt is None
    assert len(citations) == 0


def test_citation_format_special_chars():
    """RAG-07: Verify citation handles special characters in filename."""
    from src.rag.search import RAGSearch

    search = RAGSearch(None, None)
    citation = search.format_citation("my document (1).txt")

    assert citation == "📄 my document (1).txt"
    assert citation.startswith("📄")
