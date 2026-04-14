"""Document chunking for RAG processing."""

from dataclasses import dataclass
from pathlib import Path
from typing import List

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DocumentChunk:
    """Represents a document chunk with text and metadata."""

    text: str
    start: int
    end: int
    metadata: dict  # source, chunk_index, total_chunks


class DocumentChunker:
    """Splits documents into overlapping chunks for RAG processing."""

    CHUNK_SIZE = 750  # characters
    OVERLAP_RATIO = 0.15  # 15% overlap = ~112 chars
    MIN_CHUNK_SIZE = 100  # minimum chunk size before merging

    def __init__(self):
        self.overlap_chars = int(self.CHUNK_SIZE * self.OVERLAP_RATIO)

    def parse_txt(self, filepath: Path) -> str:
        """Read a text file with encoding detection.

        Args:
            filepath: Path to the text file

        Returns:
            File contents as string
        """
        # Try UTF-8 first
        try:
            return filepath.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning("UTF-8 decode failed, trying latin-1", filepath=str(filepath))

        # Fallback to latin-1
        try:
            return filepath.read_text(encoding="latin-1")
        except Exception as e:
            logger.error("Failed to parse txt file", filepath=str(filepath), error=str(e))
            return ""

    def chunk_text(self, text: str, source: str) -> List[DocumentChunk]:
        """Split text into overlapping chunks.

        Args:
            text: Full text content
            source: Source filename for metadata

        Returns:
            List of DocumentChunk objects
        """
        if not text or not text.strip():
            logger.warning("chunk_text called with empty text", source=source)
            return []

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + self.CHUNK_SIZE
            chunk_text = text[start:end]

            # Check if this is the last chunk and it's too small
            if len(chunk_text) < self.MIN_CHUNK_SIZE and chunks:
                # Merge with previous chunk
                chunks[-1].text += chunk_text
                chunks[-1].end = start + len(chunk_text)
                break

            chunk = DocumentChunk(
                text=chunk_text,
                start=start,
                end=min(end, len(text)),
                metadata={
                    "source": source,
                    "chunk_index": chunk_index,
                    "total_chunks": 0,  # Will be updated after we know total
                },
            )
            chunks.append(chunk)
            chunk_index += 1

            # Slide with overlap
            start = end - self.overlap_chars

        # Update total_chunks in metadata
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk.metadata["total_chunks"] = total_chunks

        logger.info("chunked_document", source=source, chunk_count=len(chunks))
        return chunks

    def chunk_file(self, filepath: Path) -> List[DocumentChunk]:
        """Parse a text file and return its chunks.

        Args:
            filepath: Path to the text file

        Returns:
            List of DocumentChunk objects
        """
        text = self.parse_txt(filepath)
        if not text:
            return []

        return self.chunk_text(text, source=filepath.name)
