"""RAG search integration with LLM answering and citation formatting."""

from typing import List, Dict, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class RAGSearch:
    """RAG search integration with LLM answering and citation display."""

    CITATION_FORMAT = "📄 {filename}"

    def __init__(self, rag_manager, suggestion_generator):
        """Initialize RAG search.

        Args:
            rag_manager: RAGManager instance for vector search
            suggestion_generator: AISuggestionGenerator instance for AI responses
        """
        self.rag_manager = rag_manager
        self.suggestion_generator = suggestion_generator

    def format_citation(self, filename: str) -> str:
        """Format citation badge.

        Args:
            filename: Document filename

        Returns:
            Formatted citation string (e.g., "📄 document.txt")
        """
        return self.CITATION_FORMAT.format(filename=filename)

    def build_rag_prompt(self, question: str, search_results: List[Dict]) -> tuple:
        """Build prompt with retrieved context and citation sources.

        Args:
            question: User question
            search_results: List of search result dicts with text, source, distance

        Returns:
            Tuple of (prompt, list of citation strings)
        """
        if not search_results:
            return None, []

        context_parts = []
        citations = []

        for result in search_results:
            source = result.get("source", "unknown")
            text = result.get("text", "")
            if text:
                context_parts.append(f"[Source: {source}]\n{text}")
                citations.append(self.format_citation(source))

        context = "\n\n".join(context_parts)

        prompt = f"""You are a helpful assistant. Use the following context to answer the question.

Context:
{context}

Question: {question}

Answer based on the context above. If the context doesn't contain relevant information, say so."""

        return prompt, citations

    async def answer_with_context(self, question: str, top_k: int = 5) -> Optional[Dict]:
        """Search documents and generate AI answer with context.

        Args:
            question: User question
            top_k: Number of top results to retrieve

        Returns:
            Dict with answer, citations, and has_context flag:
            {answer: str, citations: List[str], has_context: bool}
        """
        # Search for relevant chunks
        search_results = await self._search_sync(question, top_k)

        if not search_results:
            return {"answer": None, "citations": [], "has_context": False}

        # Build prompt with context
        prompt, citations = self.build_rag_prompt(question, search_results)

        # Build context for LLM
        context_for_llm = [{"text": r["text"], "source": r["source"]} for r in search_results]

        # Generate response via LLM
        answer = await self.suggestion_generator.generate_response(
            question, context=context_for_llm
        )

        return {"answer": answer, "citations": citations, "has_context": True}

    async def _search_sync(self, query: str, top_k: int) -> List[Dict]:
        """Synchronous wrapper for search (runs in event loop).

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of search result dicts
        """
        results = []

        def capture_results(r):
            nonlocal results
            results = r

        # Connect signal and trigger search
        self.rag_manager.search_complete.connect(capture_results)
        self.rag_manager.search(query, top_k)

        # Return results (in actual async usage, would use QEventLoop)
        return results
