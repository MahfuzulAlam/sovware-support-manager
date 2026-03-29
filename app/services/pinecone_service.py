"""Pinecone vector store service for RAG chunk retrieval."""

import logging
from typing import Any, Dict, List, Optional

from pinecone import Pinecone

from app.config import settings
from app.services.ai_models import embed_query

logger = logging.getLogger(__name__)

TIER_TOP_K: Dict[int, int] = {
    1: 3,
    2: 5,
    3: 8,
    4: 10,
}


class PineconeService:
    """Pinecone vector search for Directorist documentation chunks."""

    def __init__(self) -> None:
        self.client: Optional[Pinecone] = None
        self.index: Optional[Any] = None
        if settings.pinecone_api_key:
            self.client = Pinecone(api_key=settings.pinecone_api_key)
            self.index_name = settings.pinecone_index_name
            self.namespace = settings.pinecone_namespace
            self.index = self.client.Index(self.index_name)
        else:
            self.index_name = settings.pinecone_index_name
            self.namespace = settings.pinecone_namespace

    async def search(
        self,
        query_text: str,
        tier: int = 2,
        top_k: Optional[int] = None,
        namespace: Optional[str] = None,
        min_score: float = 0.70,
    ) -> List[Dict[str, Any]]:
        """
        Embed query and retrieve matching chunks from Pinecone.

        Args:
            query_text: Raw user query
            tier: Query tier (1–4); used to compute top_k if not provided
            top_k: Number of chunks to retrieve (default: from TIER_TOP_K)
            namespace: Pinecone namespace (default: from config)
            min_score: Minimum similarity score (0.0–1.0); default 0.70

        Returns:
            List of chunks. Each chunk: {id, score, text, source, section, url}

        Raises:
            ValueError: If embedding or query fails
            Exception: On Pinecone API errors
        """
        if not self.client or not self.index:
            raise ValueError("PINECONE_API_KEY is required for Pinecone search")

        if not query_text or not query_text.strip():
            logger.warning("Empty query_text for Pinecone search")
            return []

        if top_k is None:
            top_k = TIER_TOP_K.get(tier, 5)

        ns = namespace or self.namespace

        try:
            embedding = await embed_query(query_text)
        except Exception as e:
            logger.error("Failed to embed query for Pinecone: %s", e)
            raise ValueError(f"Embedding failed: {e}") from e

        try:
            logger.info(
                "Pinecone query (index=%s, namespace=%s, top_k=%d, min_score=%.2f)",
                self.index_name,
                ns,
                top_k,
                min_score,
            )
            response = self.index.query(
                vector=embedding,
                top_k=top_k,
                namespace=ns,
                include_metadata=True,
            )
        except Exception as e:
            logger.error("Pinecone query API error: %s", e)
            raise

        matches = response.get("matches") or []
        chunks: List[Dict[str, Any]] = []

        for match in matches:
            score = match.get("score", 0.0)
            if score < min_score:
                continue

            metadata = match.get("metadata") or {}
            chunk = {
                "id": match.get("id", ""),
                "score": score,
                "text": metadata.get("text", ""),
                "source": metadata.get("source", ""),
                "section": metadata.get("section", ""),
                "url": metadata.get("url", ""),
            }
            chunks.append(chunk)

        if len(chunks) < 2:
            logger.warning(
                "Pinecone returned %d chunks above min_score=%.2f (total matches=%d); context may be insufficient",
                len(chunks),
                min_score,
                len(matches),
            )

        return chunks


pinecone_service = PineconeService()
