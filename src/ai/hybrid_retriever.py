"""
Advanced Hybrid Retriever for NakshatraAI.
Combines: Semantic (ChromaDB) + Keyword (BM25) + HyDE
"""

import numpy as np
from typing import List, Dict, Optional
from langchain_core.documents import Document


class HybridRetriever:
    """Hybrid retriever with adaptive weighting."""
    
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
        """Lazy build BM25 index on first use."""
        if self._bm25_built:
            return
        
        try:
            from rank_bm25 import BM25Okapi
            print("[BM25] Building index (first time)...")
            docs = self.vector_store.similarity_search("", k=10000)
            if docs:
                tokenized = [doc.page_content.lower().split() for doc in docs]
                self.bm25_index = BM25Okapi(tokenized)
                self.bm25_documents = docs
                print(f"[BM25] Built with {len(docs)} docs")
            self._bm25_built = True
        except ImportError:
            print("[BM25] rank-bm25 not installed, skipping")
            self._bm25_built = True  # Don't try again
        except Exception as e:
            print(f"[BM25] Error: {e}")
            self._bm25_built = True  # Don't try again
    
    def retrieve(self, query: str, intent: str = "DEFAULT", top_k: int = 5, filters: Optional[Dict] = None, language: str = "en") -> List[Document]:
        """Main retrieval method with cross-lingual support."""
        print(f"[HYBRID] Intent: {intent}, Language: {language}")
        
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
        try:
            prompt = f"As an expert Vedic astrologer, briefly answer: {query}"
            response = self.llm.invoke(prompt)
            return (response.content if hasattr(response, 'content') else str(response))[:300]
        except:
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


if __name__ == "__main__":
    print("HybridRetriever class loaded successfully")