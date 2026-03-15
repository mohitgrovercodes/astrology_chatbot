# src/rag/memory_retriever.py
import logging
import uuid
from typing import Any, Dict, List, Optional

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)


class MemoryRetriever:
    """Long-term conversation memory using a dedicated Chroma collection."""

    def __init__(
        self,
        persist_directory: str = "data/vectordb",
        collection_name: str = "conversation_memories",
        embeddings=None,
    ):
        self.embeddings = embeddings or OpenAIEmbeddings(model="text-embedding-3-large")
        self.vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory,
        )

    def add_memory(
        self,
        user_id: str,
        content: str,
        role: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        meta = metadata or {}
        meta["user_id"] = user_id
        meta["role"] = role

        self.vector_store.add_texts(
            texts=[content],
            metadatas=[meta],
            ids=[str(uuid.uuid4())],
        )
        logger.debug("[MEMORY] Stored segment for user %s", user_id)

    def retrieve_memories(self, user_id: str, query: str, k: int = 3) -> List[Dict[str, Any]]:
        try:
            results = self.vector_store.similarity_search(query, k=k, filter={"user_id": user_id})
            return [{"content": r.page_content, "metadata": r.metadata} for r in results]
        except Exception as exc:
            logger.debug("[MEMORY] retrieval failed: %s", exc)
            return []
