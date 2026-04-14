"""Pytest fixtures for RAG tests."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock


@pytest.fixture
def sample_text():
    """Sample text with enough content for multiple chunks."""
    return "This is a sample document with enough text to create multiple chunks. " * 20


@pytest.fixture
def sample_text_short():
    """Short text that should result in a single chunk."""
    return "Short piece of text."


@pytest.fixture
def mock_chromadb(monkeypatch):
    """Mock ChromaDB client for unit tests."""
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [["chunk_0", "chunk_1"]],
        "documents": [["text 1", "text 2"]],
        "metadatas": [[{"source": "test.txt"}], [{"source": "test.txt"}]],
        "distances": [[0.1, 0.2]],
    }
    mock_collection.get.return_value = {
        "ids": [],
        "documents": [],
        "metadatas": [],
        "distances": [],
    }
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection

    import chromadb

    monkeypatch.setattr(chromadb, "PersistentClient", lambda **kwargs: mock_client)
    monkeypatch.setattr(chromadb, "Settings", Mock())
    return mock_client


@pytest.fixture
def mock_embedding_model(monkeypatch):
    """Mock sentence-transformers model."""
    import numpy as np

    mock_model = Mock()
    mock_model.encode.return_value = np.zeros((1, 384), dtype=np.float32)
    monkeypatch.setattr(
        "sentence_transformers.SentenceTransformer", lambda *args, **kwargs: mock_model
    )
    return mock_model


@pytest.fixture
def temp_txt_file(tmp_path, sample_text):
    """Create a temporary txt file for testing."""
    txt_file = tmp_path / "test.txt"
    txt_file.write_text(sample_text)
    return txt_file
