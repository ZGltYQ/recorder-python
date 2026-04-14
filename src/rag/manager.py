"""ChromaDB-based RAG document manager."""

from typing import List, Dict, Optional
from PySide6.QtCore import QObject, Signal

from ..utils.logger import get_logger
from ..utils.config import get_config

logger = get_logger(__name__)


class RAGManager(QObject):
    """RAG operations manager with Qt signals for ChromaDB operations."""

    # Signals
    indexing_progress = Signal(int, int)  # (current, total chunks)
    indexing_complete = Signal(str)  # (document_id)
    search_complete = Signal(list)  # List of result dicts with text, source, distance
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._client = None
        self._collection = None
        self._initialize()

    def _initialize(self):
        """Initialize ChromaDB client and collection."""
        try:
            import chromadb
            from chromadb.config import Settings

            data_dir = get_config().get_data_dir()
            chromadb_path = data_dir / "chromadb"

            logger.info("Initializing ChromaDB", path=str(chromadb_path))

            self._client = chromadb.PersistentClient(
                path=str(chromadb_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )
            self._collection = self._client.get_or_create_collection(
                name="documents", metadata={"description": "RAG document chunks"}
            )
            logger.info("ChromaDB initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize ChromaDB", error=str(e))
            self.error.emit(f"Failed to initialize ChromaDB: {e}")

    @property
    def collection(self):
        """Get the ChromaDB collection."""
        return self._collection

    def add_document(
        self, document_id: str, chunks: List[Dict], embeddings: List[List[float]]
    ) -> bool:
        """Add document chunks with pre-computed embeddings to the collection.

        Args:
            document_id: Unique identifier for the document
            chunks: List of chunk dicts with 'text' and 'metadata' keys
            embeddings: List of embedding vectors (list of floats)

        Returns:
            True if successful, False otherwise
        """
        try:
            if not chunks or not embeddings:
                logger.warning("add_document called with empty chunks or embeddings")
                return False

            # Build IDs, documents, and metadata lists
            ids = [f"{document_id}_{i}" for i in range(len(chunks))]
            documents = [chunk.get("text", "") for chunk in chunks]
            metadatas = [chunk.get("metadata", {}) for chunk in chunks]

            # Add to collection
            self._collection.add(
                ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
            )

            logger.info("Document indexed", document_id=document_id, chunk_count=len(chunks))
            self.indexing_complete.emit(document_id)
            return True

        except Exception as e:
            logger.error("Failed to add document", document_id=document_id, error=str(e))
            self.error.emit(str(e))
            return False

    def delete_document(self, document_id: str) -> bool:
        """Delete all chunks for a document.

        Args:
            document_id: Document ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find all chunk IDs for this document
            chunk_ids = []
            for i in range(1000):  # Reasonable max chunks
                chunk_id = f"{document_id}_{i}"
                try:
                    # Try to get the chunk to check if it exists
                    self._collection.get(ids=[chunk_id])
                    chunk_ids.append(chunk_id)
                except Exception:
                    # Chunk doesn't exist, we've reached the end
                    break

            if chunk_ids:
                self._collection.delete(ids=chunk_ids)
                logger.info(
                    "Document deleted", document_id=document_id, chunks_deleted=len(chunk_ids)
                )
            else:
                logger.warning("No chunks found for document", document_id=document_id)

            return True

        except Exception as e:
            logger.error("Failed to delete document", document_id=document_id, error=str(e))
            self.error.emit(str(e))
            return False

    def get_document_chunks(self, document_id: str) -> List[Dict]:
        """Retrieve all chunks for a document.

        Args:
            document_id: Document ID

        Returns:
            List of chunk dicts with text, start, end, metadata
        """
        try:
            # Get all chunks with IDs starting with document_id_
            # Note: ChromaDB doesn't support prefix queries directly,
            # so we iterate through potential chunk indices
            chunks = []
            for i in range(1000):
                chunk_id = f"{document_id}_{i}"
                try:
                    result = self._collection.get(ids=[chunk_id])
                    if result["ids"]:
                        chunks.append(
                            {
                                "id": result["ids"][0],
                                "text": result["documents"][0] if result["documents"] else "",
                                "metadata": result["metadatas"][0] if result["metadatas"] else {},
                            }
                        )
                except Exception:
                    break
            return chunks

        except Exception as e:
            logger.error("Failed to get document chunks", document_id=document_id, error=str(e))
            return []

    def list_documents(self) -> List[Dict]:
        """List all unique documents in the collection.

        Returns:
            List of dicts with document_id and metadata
        """
        try:
            # Get all items and extract unique sources
            all_data = self._collection.get()
            documents_map = {}

            if all_data and all_data.get("metadatas"):
                for i, metadata in enumerate(all_data["metadatas"]):
                    source = metadata.get("source", "unknown") if metadata else "unknown"
                    if source not in documents_map:
                        documents_map[source] = {
                            "document_id": source,
                            "source": source,
                            "chunk_count": 0,
                        }
                    documents_map[source]["chunk_count"] += 1

            return list(documents_map.values())

        except Exception as e:
            logger.error("Failed to list documents", error=str(e))
            return []

    def search(self, query: str, top_k: int = 5):
        """Search for relevant document chunks.

        Args:
            query: Search query string
            top_k: Number of top results to return
        """
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
            formatted = self._format_search_results(results)
            self.search_complete.emit(formatted)

        except Exception as e:
            logger.error("search_failed", error=str(e))
            self.error.emit(str(e))

    def _format_search_results(self, results) -> List[Dict]:
        """Format ChromaDB query results.

        Args:
            results: Raw ChromaDB query results

        Returns:
            List of formatted result dicts
        """
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                formatted.append(
                    {
                        "id": doc_id,
                        "text": results["documents"][0][i] if results["documents"] else "",
                        "source": results["metadatas"][0][i].get("source", "unknown")
                        if results["metadatas"]
                        else "unknown",
                        "distance": results["distances"][0][i] if results["distances"] else 0.0,
                    }
                )
        return formatted
