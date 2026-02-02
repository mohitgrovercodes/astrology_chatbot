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
        self._build_bm25_index()
    
    def _build_bm25_index(self):
        """Build BM25 index."""
        try:
            from rank_bm25 import BM25Okapi
            print("[BM25] Building index...")
            docs = self.vector_store.similarity_search("", k=10000)
            if docs:
                tokenized = [doc.page_content.lower().split() for doc in docs]
                self.bm25_index = BM25Okapi(tokenized)
                self.bm25_documents = docs
                print(f"[BM25] Built with {len(docs)} docs")
        except ImportError:
            print("[BM25] rank-bm25 not installed, skipping")
        except Exception as e:
            print(f"[BM25] Error: {e}")
    
    def retrieve(self, query: str, intent: str = "DEFAULT", top_k: int = 5, filters: Optional[Dict] = None) -> List[Document]:
        """Main retrieval method."""
        print(f"[HYBRID] Intent: {intent}")
        sem_w, key_w, hyde_w = self.WEIGHTS_BY_INTENT.get(intent, self.WEIGHTS_BY_INTENT["DEFAULT"])
        
        semantic = self._semantic_search(query, k=15, filters=filters)
        keyword = self._keyword_search(query, k=15)
        hyde = self._hyde_search(query, k=15, filters=filters)
        
        fused = self._reciprocal_rank_fusion([semantic, keyword, hyde], [sem_w, key_w, hyde_w])
        return fused[:top_k]
    
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