# src/ai/hybrid_retriever.py
"""
Advanced Hybrid Retriever for NakshatraAI.
Combines semantic search, BM25 keyword search, optional HyDE,
and optional cross-encoder reranking.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from langchain_core.documents import Document

from config.rag_config import RAGConfig

try:
    from src.rag.retriever import RetrievedChunk
    _RETRIEVED_CHUNK_AVAILABLE = True
except Exception:
    RetrievedChunk = None
    _RETRIEVED_CHUNK_AVAILABLE = False


logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid retriever with adaptive weighting and optional reranking."""

    def __init__(
        self,
        vector_store,
        llm,
        enable_memory: bool = True,
        memory_collection: str = "conversation_memories",
    ):
        self.vector_store = vector_store
        self.llm = llm
        self.bm25_index = None
        self.bm25_documents: List[Document] = []
        self._bm25_built = False

        self.reranker = None
        if RAGConfig.USE_RERANKING and RAGConfig.ENABLE_RERANKING:
            try:
                from src.rag.reranker import Reranker
                self.reranker = Reranker(model=RAGConfig.RERANKER_MODEL)
                logger.info("[HYBRID] Reranker initialized")
            except Exception as exc:
                logger.warning(f"[HYBRID] Reranker unavailable: {exc}")

        self.memory_retriever = None
        if enable_memory:
            try:
                from src.rag.memory_retriever import MemoryRetriever
                self.memory_retriever = MemoryRetriever(collection_name=memory_collection)
                logger.info("[HYBRID] Memory retriever initialized")
            except Exception as exc:
                logger.warning(f"[HYBRID] Memory retriever unavailable: {exc}")

        logger.info("[HYBRID] Retriever initialized (BM25 lazy build)")

    def _ensure_bm25_built(self) -> None:
        if self._bm25_built:
            return

        self._bm25_built = True
        try:
            from rank_bm25 import BM25Okapi
            collection = getattr(self.vector_store, "_collection", None)
            if collection is None:
                logger.info("[BM25] No direct collection handle; skipping BM25")
                return

            total_count = int(collection.count())
            if total_count <= 0:
                return

            all_docs: List[Document] = []
            batch_size = 1000
            offset = 0
            cap = min(total_count, 10000)
            while offset < cap:
                batch = collection.get(limit=batch_size, offset=offset)
                docs = batch.get("documents") or []
                metas = batch.get("metadatas") or []
                if not docs:
                    break
                if not metas:
                    metas = [{} for _ in docs]
                all_docs.extend(Document(page_content=t, metadata=(m or {})) for t, m in zip(docs, metas))
                offset += batch_size

            if not all_docs:
                return

            tokenized = [d.page_content.lower().split() for d in all_docs]
            self.bm25_index = BM25Okapi(tokenized)
            self.bm25_documents = all_docs
            logger.info(f"[BM25] Built with {len(all_docs)} docs")
        except Exception as exc:
            logger.warning(f"[BM25] Build failed: {exc}")

    def retrieve(
        self,
        query: str,
        intent: str = "DEFAULT",
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None,
        language: str = "en",
        content_type: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Document]:
        if top_k is None:
            top_k = RAGConfig.get_top_k(content_type=content_type)

        search_query = self._translate_to_english(query) if language != "en" else query
        candidate_k = max(top_k * 2, 12)
        content_type = content_type or self._infer_content_type(intent)

        self._ensure_bm25_built()

        sem_w, key_w, hyde_w = RAGConfig.get_hybrid_weights(intent)
        semantic = self._semantic_search(search_query, k=candidate_k, filters=filters)
        keyword = self._keyword_search(search_query, k=candidate_k)
        hyde = self._hyde_search(search_query, k=candidate_k, filters=filters) if RAGConfig.USE_HYDE else []

        fused_docs, fused_scores = self._reciprocal_rank_fusion(
            [semantic, keyword, hyde],
            [sem_w, key_w, hyde_w],
            k=RAGConfig.RECIPROCAL_RANK_K,
        )

        if user_id and self.memory_retriever:
            fused_docs = self._inject_memory_hits(fused_docs, query, user_id=user_id)

        top_score = max(fused_scores.values()) if fused_scores else 0.0
        if self._should_rerank(content_type, top_score, query) and self.reranker and _RETRIEVED_CHUNK_AVAILABLE:
            reranked = self._rerank_documents(query, fused_docs, top_k=top_k, content_type=content_type)
        else:
            reranked = fused_docs[:top_k]

        if RAGConfig.should_expand(content_type=content_type, chunks=None, query=query):
            reranked = self._expand_with_adjacent_chunks(reranked, max_related=RAGConfig.MAX_ADJACENT_CHUNKS)

        return self._dedupe_docs(reranked)[:top_k]

    def _should_rerank(self, content_type: Optional[str], top_score: float, query: str) -> bool:
        if not self.reranker:
            return False
        try:
            return RAGConfig.should_rerank(content_type=content_type, top_score=top_score, query=query)
        except Exception:
            return False

    def _infer_content_type(self, intent: str) -> str:
        intent = (intent or "").upper()
        if intent in {"PREDICTION", "RAG_WITH_CALCULATION", "INTERPRETATION"}:
            return "interpretation"
        if intent in {"CHITCHAT"}:
            return "chitchat"
        return "general"

    def _translate_to_english(self, query: str) -> str:
        try:
            prompt = (
                "Translate the following astrological query to English for retrieval. "
                "Keep technical terms accurate. Return ONLY the translation.\n"
                f"Query: {query}\n"
                "Translation:"
            )
            response = self.llm.invoke(prompt)
            return response.content.strip() if hasattr(response, "content") else str(response).strip()
        except Exception as exc:
            logger.debug(f"[HYBRID] Translation error: {exc}")
            return query

    def _semantic_search(self, query: str, k: int, filters: Optional[Dict]) -> List[Document]:
        try:
            return self.vector_store.similarity_search(query, k=k, filter=filters)
        except Exception as exc:
            logger.warning(f"[SEMANTIC] Error: {exc}")
            return []

    def _keyword_search(self, query: str, k: int) -> List[Document]:
        if not self.bm25_index:
            return []
        try:
            tokens = query.lower().split()
            scores = self.bm25_index.get_scores(tokens)
            top_idx = np.argsort(scores)[::-1][:k]
            return [self.bm25_documents[idx] for idx in top_idx if scores[idx] > 0]
        except Exception as exc:
            logger.warning(f"[KEYWORD] Error: {exc}")
            return []

    def _hyde_search(self, query: str, k: int, filters: Optional[Dict]) -> List[Document]:
        try:
            hypo = self._generate_hypothetical_answer(query)
            if hypo:
                return self.vector_store.similarity_search(hypo, k=k, filter=filters)
        except Exception as exc:
            logger.warning(f"[HYDE] Error: {exc}")
        return []

    def _generate_hypothetical_answer(self, query: str) -> Optional[str]:
        try:
            prompt = (
                "You are producing a passage for a Vedic astrology reference database.\n"
                "Write a short (3-5 sentence), factual paragraph that an astrology text\n"
                "would contain to answer the following question. Use precise terminology\n"
                "(houses, planets, dasha, yoga names). Avoid first-person wording.\n\n"
                f"Question: {query}\n\n"
                "Classical text passage:"
            )
            response = self.llm.invoke(prompt)
            raw = (response.content if hasattr(response, "content") else str(response)).strip()
            return raw[:450]
        except Exception:
            return None

    def _reciprocal_rank_fusion(
        self,
        result_lists: List[List[Document]],
        weights: List[float],
        k: int = 60,
    ) -> Tuple[List[Document], Dict[int, float]]:
        scores: Dict[int, float] = {}
        docs_map: Dict[int, Document] = {}

        for results, weight in zip(result_lists, weights):
            for rank, doc in enumerate(results, 1):
                doc_id = hash(doc.page_content)
                scores[doc_id] = scores.get(doc_id, 0.0) + (weight / (k + rank))
                docs_map[doc_id] = doc

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [docs_map[doc_id] for doc_id, _ in ranked], scores

    def _rerank_documents(self, query: str, docs: List[Document], top_k: int, content_type: Optional[str]) -> List[Document]:
        chunks = [self._document_to_chunk(d, rank=i) for i, d in enumerate(docs)]
        reranked_chunks = self.reranker.rerank(query=query, chunks=chunks, top_k=top_k, content_type=content_type)
        return [Document(page_content=c.text, metadata={**(c.metadata or {}), "rerank_score": c.score}) for c in reranked_chunks]

    def _expand_with_adjacent_chunks(self, docs: List[Document], max_related: int = 1) -> List[Document]:
        collection = getattr(self.vector_store, "_collection", None)
        if collection is None or not docs:
            return docs

        expanded = list(docs)
        seen = {hash(d.page_content) for d in docs}

        for doc in docs:
            meta = doc.metadata or {}
            source_book = meta.get("source_book")
            chapter = meta.get("chapter")
            chunk_index = meta.get("chunk_index")
            if source_book is None or chapter is None or chunk_index is None:
                continue

            for offset in range(-max_related, max_related + 1):
                if offset == 0:
                    continue
                adjacent_index = chunk_index + offset
                try:
                    where_clause = {
                        "$and": [
                            {"source_book": {"$eq": source_book}},
                            {"chapter": {"$eq": chapter}},
                            {"chunk_index": {"$eq": adjacent_index}},
                        ]
                    }
                    res = collection.get(where=where_clause, limit=1, include=["documents", "metadatas"])
                    if not res or not res.get("documents"):
                        continue
                    text = res["documents"][0]
                    key = hash(text)
                    if key in seen:
                        continue
                    m = (res.get("metadatas") or [{}])[0] or {}
                    expanded.append(Document(page_content=text, metadata=m))
                    seen.add(key)
                except Exception:
                    continue

        return expanded

    def _inject_memory_hits(self, docs: List[Document], query: str, user_id: str) -> List[Document]:
        try:
            memories = self.memory_retriever.retrieve_memories(user_id=user_id, query=query, k=2)
            memory_docs = [
                Document(
                    page_content=m.get("content", ""),
                    metadata={**(m.get("metadata") or {}), "source_book": "conversation_memory", "memory_hit": True},
                )
                for m in memories
                if m.get("content")
            ]
            return self._dedupe_docs(docs + memory_docs)
        except Exception as exc:
            logger.debug(f"[MEMORY] Inject failed: {exc}")
            return docs

    def _dedupe_docs(self, docs: List[Document]) -> List[Document]:
        out: List[Document] = []
        seen = set()
        for d in docs:
            key = hash(d.page_content)
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
        return out

    def retrieve_as_chunks(
        self,
        query: str,
        intent: str = "DEFAULT",
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None,
        language: str = "en",
        content_type: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        documents = self.retrieve(
            query=query,
            intent=intent,
            top_k=top_k,
            filters=filters,
            language=language,
            content_type=content_type,
            user_id=user_id,
        )
        if not _RETRIEVED_CHUNK_AVAILABLE:
            return documents
        return [self._document_to_chunk(doc, rank) for rank, doc in enumerate(documents)]

    def _document_to_chunk(self, doc: Document, rank: int = 0):
        meta = doc.metadata if doc.metadata else {}
        score = 1.0 / (1.0 + rank)
        return RetrievedChunk(
            chunk_id=meta.get("chunk_id", str(hash(doc.page_content))),
            text=doc.page_content,
            display_text=meta.get("display_text", doc.page_content),
            verse_sanskrit=meta.get("verse_sanskrit"),
            score=score,
            metadata=meta,
        )


if __name__ == "__main__":
    print("HybridRetriever class loaded successfully")
