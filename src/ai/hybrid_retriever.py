# src/ai/hybrid_retriever.py
# src\ai\hybrid_retriever.py
"""
Advanced Hybrid Retriever for NakshatraAI.
Combines: Semantic (ChromaDB) + Keyword (BM25) + HyDE
"""

import numpy as np
from typing import List, Dict, Optional
from langchain_core.documents import Document
from config.rag_config import RAGConfig

# Import RetrievedChunk for the retrieve_as_chunks() adapter
try:
    from src.rag.retriever import RetrievedChunk
    _RETRIEVED_CHUNK_AVAILABLE = True
except ImportError:
    _RETRIEVED_CHUNK_AVAILABLE = False

class HybridRetriever:
    """
    Hybrid retriever with adaptive weighting.

    Primary retrieval backend for the production orchestrator.
    Also supports RAGEngine integration via retrieve_as_chunks().

    Retrieval strategies (all fused with RRF):
      - Semantic  : ChromaDB vector similarity search
      - Keyword   : BM25 full-text search (lazy-built on first call)
      - HyDE      : Hypothetical Document Embedding (LLM-generated answer as query)
    """
    
    WEIGHTS_BY_INTENT = {
        "PREDICTION": (0.5, 0.3, 0.2),
        "INTERPRETATION": (0.5, 0.25, 0.25),
        "LEARNING": (0.5, 0.3, 0.2),
        "DEFAULT": (0.5, 0.3, 0.2)
    }
    
    def __init__(self, vector_store, llm):
        self.vector_store = vector_store
        self.llm = llm
        self.bm25_index = None
        self.bm25_documents = []
        self._bm25_built = False  # Track if BM25 was built
        # Don't build BM25 index immediately - do it on first use
        print("[HYBRID] Retriever initialized (BM25 will build on first RAG query)")
    
    
    def _ensure_bm25_built(self):
        """Lazy build BM25 index with pagination and multiple strategies."""
        if self._bm25_built:
            return
        
        try:
            from rank_bm25 import BM25Okapi
            from langchain.schema import Document
            print("[BM25] Building index (first time)...")
            
            all_docs = []
            
            # Strategy 1: Direct collection access with pagination (most reliable)
            try:
                print("[BM25] Strategy 1: Direct collection access with pagination...")
                collection = self.vector_store._collection
                total_count = collection.count()
                print(f"[BM25] Total documents in collection: {total_count}")
                
                batch_size = 1000
                offset = 0
                
                while offset < min(total_count, 10000):  # Limit to 10k docs
                    try:
                        batch = collection.get(limit=batch_size, offset=offset)
                        if batch and batch.get('documents'):
                            batch_docs = [
                                Document(page_content=text, metadata=meta or {})
                                for text, meta in zip(batch['documents'], batch.get('metadatas', [{}] * len(batch['documents'])))
                            ]
                            all_docs.extend(batch_docs)
                            offset += batch_size
                            if offset % 5000 == 0:
                                print(f"[BM25] Loaded {len(all_docs)} docs so far...")
                        else:
                            break
                    except Exception as e:
                        print(f"[BM25] Batch at offset {offset} failed: {e}")
                        break
                
                if all_docs:
                    print(f"[BM25] Strategy 1 succeeded: {len(all_docs)} docs")
            except Exception as e:
                print(f"[BM25] Strategy 1 failed: {e}")
            
            # Strategy 2: Generic query (fallback)
            if not all_docs:
                try:
                    print("[BM25] Strategy 2: Generic query...")
                    all_docs = self.vector_store.similarity_search("astrology", k=10000)
                    if all_docs:
                        print(f"[BM25] Strategy 2 succeeded: {len(all_docs)} docs")
                except Exception as e:
                    print(f"[BM25] Strategy 2 failed: {e}")
            
            # Strategy 3: Small query and expand (last resort)
            if not all_docs:
                try:
                    print("[BM25] Strategy 3: Small query expansion...")
                    queries = ["marriage", "career", "health", "astrology", "birth chart"]
                    seen_ids = set()
                    
                    for query in queries:
                        results = self.vector_store.similarity_search(query, k=2000)
                        for doc in results:
                            doc_id = hash(doc.page_content)
                            if doc_id not in seen_ids:
                                all_docs.append(doc)
                                seen_ids.add(doc_id)
                    
                    if all_docs:
                        print(f"[BM25] Strategy 3 succeeded: {len(all_docs)} unique docs")
                except Exception as e:
                    print(f"[BM25] Strategy 3 failed: {e}")
            
            # Build index if we got documents
            if all_docs:
                tokenized = [doc.page_content.lower().split() for doc in all_docs]
                self.bm25_index = BM25Okapi(tokenized)
                self.bm25_documents = all_docs
                print(f"[BM25] ✅ Successfully built index with {len(all_docs)} documents")
            else:
                print("[BM25] ❌ All strategies failed - proceeding with vector search only")
            
            self._bm25_built = True
            
        except ImportError:
            print("[BM25] rank-bm25 not installed, skipping")
            self._bm25_built = True
        except Exception as e:
            print(f"[BM25] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self._bm25_built = True
    
    def retrieve(self, query: str, intent: str = "DEFAULT", top_k: int = None, filters: Optional[Dict] = None, language: str = "en", content_type: str = None,) -> List[Document]:
        """Main retrieval method with cross-lingual support."""
        # Get top_k from RAGConfig if not provided
        if top_k is None:
            top_k = RAGConfig.get_top_k(content_type=content_type)
    
        print(f"[HYBRID] Intent: {intent}, Language: {language}, top_k: {top_k}")
        
        # Step 1: Query Translation (Cross-lingual RAG)
        # We find English text using an English version of the query
        search_query = query
        if language != "en":
            print(f"[HYBRID] Translating non-English query to English for retrieval...")
            search_query = self._translate_to_english(query)
            print(f"[HYBRID] Translated: '{search_query}'")

        # Ensure BM25 index is built (lazy initialization)
        self._ensure_bm25_built()
        
        sem_w, key_w, hyde_w = self.WEIGHTS_BY_INTENT.get(intent, self.WEIGHTS_BY_INTENT["DEFAULT"])
        
        semantic = self._semantic_search(search_query, k=15, filters=filters)
        keyword = self._keyword_search(search_query, k=15)
        hyde = self._hyde_search(search_query, k=15, filters=filters)
        
        fused = self._reciprocal_rank_fusion([semantic, keyword, hyde], [sem_w, key_w, hyde_w])
        return fused[:top_k]

    def _translate_to_english(self, query: str) -> str:
        """Translate query to English using LLM for retrieval."""
        try:
            prompt = f"Translate the following astrological query to English for use in a database search. Keep technical terms accurate. Return ONLY the translation.\nQuery: {query}\nTranslation:"
            response = self.llm.invoke(prompt)
            return response.content.strip() if hasattr(response, 'content') else str(response).strip()
        except Exception as e:
            print(f"[HYBRID] Translation error: {e}")
            return query
    
    def _semantic_search(self, query: str, k: int, filters: Optional[Dict]) -> List[Document]:
        try:
            return self.vector_store.similarity_search(query, k=k, filter=filters)
        except Exception as e:
            print(f"[SEMANTIC] Error: {e}")
            return []
    
    def _keyword_search(self, query: str, k: int) -> List[Document]:
        if not self.bm25_index:
            return []
        try:
            tokens = query.lower().split()
            scores = self.bm25_index.get_scores(tokens)
            top_idx = np.argsort(scores)[::-1][:k]
            return [self.bm25_documents[idx] for idx in top_idx if scores[idx] > 0]
        except Exception as e:
            print(f"[KEYWORD] Error: {e}")
            return []
    
    def _hyde_search(self, query: str, k: int, filters: Optional[Dict]) -> List[Document]:
        try:
            hypo = self._generate_hypothetical_answer(query)
            if hypo:
                return self.vector_store.similarity_search(hypo, k=k, filter=filters)
        except Exception as e:
            print(f"[HYDE] Error: {e}")
        return []
    
    def _generate_hypothetical_answer(self, query: str) -> Optional[str]:
        """Generate a hypothetical document passage for HyDE retrieval.

        The generated passage is written in the style of a classical Vedic
        astrology text so its embedding closely matches what actually exists
        in the vector store.  A well-written HyDE passage dramatically
        improves recall quality, especially for Hindi/multilingual queries
        where the stored corpus is in English.
        """
        try:
            prompt = (
                "You are producing a passage for a Vedic astrology reference database.\n"
                "Write a short (3-5 sentence), dense, factual paragraph that a classical\n"
                "Vedic astrology textbook would contain to answer the following question.\n"
                "Use precise astrological terminology (house numbers, planet names in\n"
                "English + Sanskrit in parentheses, dasha names, yoga names) so the\n"
                "passage will match relevant scholarly chunks in retrieval.\n"
                "Do NOT add disclaimers or first-person language. Write as if excerpted\n"
                "from an authoritative text.\n\n"
                f"Question: {query}\n\n"
                "Classical text passage:"
            )
            response = self.llm.invoke(prompt)
            raw = (response.content if hasattr(response, 'content') else str(response)).strip()
            # Trim to 400 chars — longer doesn't help embedding quality
            return raw[:400]
        except Exception:
            return None

    
    def _reciprocal_rank_fusion(self, result_lists: List[List[Document]], weights: List[float], k: int = 60) -> List[Document]:
        scores = {}
        docs_map = {}
        
        for results, weight in zip(result_lists, weights):
            for rank, doc in enumerate(results, 1):
                doc_id = hash(doc.page_content)
                rrf_score = weight / (k + rank)
                scores[doc_id] = scores.get(doc_id, 0) + rrf_score
                docs_map[doc_id] = doc
        
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [docs_map[doc_id] for doc_id, _ in ranked]
        
    def retrieve_as_chunks(
        self,
        query: str,
        intent: str = "DEFAULT",
        top_k: int = None,
        filters: Optional[Dict] = None,
        language: str = "en",
        content_type: str = None,
    ):
        """
        Retrieve documents and return them as RetrievedChunk objects.

        This is the integration point for RAGEngine — it delegates to the
        authoritative retrieve() method then wraps results so they are
        compatible with downstream pipeline (reranker, context expansion,
        prompt builder).

        Returns:
            List[RetrievedChunk] if RetrievedChunk is importable, else List[Document].
        """
        documents = self.retrieve(
            query=query,
            intent=intent,
            top_k=top_k,
            filters=filters,
            language=language,
            content_type=content_type,
        )
        if not _RETRIEVED_CHUNK_AVAILABLE:
            return documents  # Graceful degradation
        return [self._document_to_chunk(doc, rank) for rank, doc in enumerate(documents)]

    def _document_to_chunk(self, doc: Document, rank: int = 0):
        """
        Convert a LangChain Document to a RetrievedChunk.

        Score is derived from rank position (best-rank = highest-score) so
        downstream reranking logic can compare chunks on equal footing.
        """
        meta = doc.metadata if doc.metadata else {}
        # Derive a pseudo-score from rank (1.0 for rank 0, decreasing)
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