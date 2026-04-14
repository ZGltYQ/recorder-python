"""Embedding worker for sentence-transformers integration."""

from typing import List
from PySide6.QtCore import QThread, Signal

from ..utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingWorker(QThread):
    """Background worker for computing embeddings with sentence-transformers."""

    # Signals
    progress = Signal(int, int)  # (current_batch, total_batches)
    complete = Signal(list)  # list of embedding vectors
    error = Signal(str)

    def __init__(self, texts: List[str]):
        """Initialize the embedding worker.

        Args:
            texts: List of text strings to embed
        """
        super().__init__()
        self.texts = texts
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        self._is_running = False

    def run(self):
        """Compute embeddings for all texts in background thread."""
        self._is_running = True

        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np

            logger.info("Loading sentence-transformers model", model=self.model_name)
            model = SentenceTransformer(self.model_name)

            # Encode texts in batches
            batch_size = 32
            total_batches = (len(self.texts) + batch_size - 1) // batch_size

            all_embeddings = []

            for batch_idx in range(total_batches):
                if not self._is_running:
                    logger.info("EmbeddingWorker stopped by user")
                    return

                start = batch_idx * batch_size
                end = min(start + batch_size, len(self.texts))
                batch_texts = self.texts[start:end]

                # Encode batch
                embeddings = model.encode(
                    batch_texts,
                    show_progress_bar=False,
                    batch_size=batch_size,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )

                # Convert to list and add to results
                for embedding in embeddings:
                    all_embeddings.append(embedding.tolist())

                # Emit progress
                self.progress.emit(batch_idx + 1, total_batches)

            logger.info("Embedding computation complete", texts_count=len(self.texts))
            self.complete.emit(all_embeddings)

        except Exception as e:
            logger.error("embedding_failed", error=str(e))
            self.error.emit(str(e))

    def stop(self):
        """Stop the embedding computation."""
        self._is_running = False
