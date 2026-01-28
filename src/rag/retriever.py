#!/usr/bin/env python3
"""
RAG Retriever for Astrology Chatbot

Advanced hybrid retrieval merging semantic search (ChromaDB), 
keyword search (BM25), and HyDE augmentation.
"""

import os
import json
import numpy as np
import chromadb
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from chromadb.config import Settings
from rank_bm25 import BM25Okapi

# Project imports
try:
    from src.utils.config import get_config
    from src.utils.logger import get_logger
    from src.rag.preprocessing.embedder import Embedder
    logger = get_logger(__name__)
    CONFIG_AVAILABLE = True
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    CONFIG_AVAILABLE = False
    # Manual import for embedder if not in package mode
    try:
        from preprocessing.embedder import Embedder
    except ImportError:
        Embedder = None

@dataclass
class RetrievedChunk:
    """Container for retrieved chunk with metadata."""
    chunk_id: str
    text: str
    display_text: str
    verse_sanskrit: Optional[str]
    score: float
    metadata: Dict[str, Any]
    
    def __str__(self):
        """String representation for display."""
        lines = []
        lines.append(f"Score: {self.score:.4f}")
        lines.append(f"Source: {self.metadata.get('source_book', 'Unknown')}")
        if self.metadata.get('chapter'):
            lines.append(f"Chapter: {self.metadata['chapter']}")
        if self.metadata.get('verse_number'):
            lines.append(f"Verse: {self.metadata['verse_number']}")
        lines.append(f"\n{self.display_text}")
        if self.verse_sanskrit:
            lines.append(f"\nSanskrit: {self.verse_sanskrit}")
        return "\n".join(lines)


class AstrologyRetriever:
    """
    Advanced Retriever supporting Semantic, BM25, Hybrid and HyDE.
    """
    
    def __init__(
        self,
        collection_name: Optional[str] = None,
        db_path: Optional[str] = None,
        embedder: Optional[Embedder] = None,
    ):
        """Initialize retriever with config defaults."""
        if CONFIG_AVAILABLE:
            config = get_config()
            self.collection_name = collection_name or config.rag.collection_name
            self.db_path = Path(db_path or config.env.chroma_persist_dir)
        else:
            self.collection_name = collection_name or "brihat_parasara_hora_sastra"
            self.db_path = Path(db_path or "data/vectordb")
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
            logger.info(f"OK: Loaded collection: {self.collection_name}")
            logger.info(f"INFO: Collection size: {self.collection.count()} chunks")
        except Exception as e:
            logger.error(f"Collection '{self.collection_name}' not found: {e}")
            self.collection = None
        
        self.embedder = embedder or Embedder()
        
        # Hybrid Search Index
        self.bm25_index = None
        self.bm25_documents = []
        self.bm25_ids = []
        self._build_bm25_index()

    def _build_bm25_index(self):
        """Build BM25 index from ChromaDB documents."""
        if not self.collection: return
        try:
            all_docs = self.collection.get(include=["documents", "metadatas"])
            if all_docs and all_docs['documents']:
                self.bm25_documents = all_docs['documents']
                self.bm25_ids = all_docs['ids']
                tokenized_docs = [doc.lower().split() for doc in self.bm25_documents]
                self.bm25_index = BM25Okapi(tokenized_docs)
                logger.info(f"OK: Built BM25 index with {len(self.bm25_documents)} documents")
        except Exception as e:
            logger.warning(f"WARN: Failed to build BM25 index: {e}")

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """Core semantic retrieval."""
        if not self.collection or not self.embedder.client:
            logger.error("Retrieval unavailable (Check DB/API Key)")
            return []
            
        where_clause = self._build_where_clause(filters) if filters else None
        query_embedding = self.embedder.embed_texts([query])[0]
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause,
            include=["documents", "metadatas", "distances"]
        )
        
        return self._parse_results(results)

    def retrieve_hybrid(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        semantic_weight: float = 0.7,
    ) -> List[RetrievedChunk]:
        """Reciprocal Rank Fusion (RRF) Hybrid Search."""
        semantic_results = self.retrieve(query, top_k=top_k * 2, filters=filters)
        
        bm25_results = []
        if self.bm25_index:
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25_index.get_scores(tokenized_query)
            top_indices = np.argsort(bm25_scores)[::-1][:top_k * 2]
            
            for idx in top_indices:
                if bm25_scores[idx] > 0:
                    chunk_id = self.bm25_ids[idx]
                    res = self.collection.get(ids=[chunk_id], include=["documents", "metadatas"])
                    if res and res['ids']:
                        m = res['metadatas'][0]
                        bm25_results.append(RetrievedChunk(
                            chunk_id=chunk_id,
                            text=res['documents'][0],
                            display_text=m.get('display_text', res['documents'][0]),
                            verse_sanskrit=m.get('verse_sanskrit'),
                            score=float(bm25_scores[idx]),
                            metadata=m
                        ))

        # RRF Fusion
        combined = {}
        for rank, c in enumerate(semantic_results, 1):
            combined[c.chunk_id] = combined.get(c.chunk_id, 0) + semantic_weight / (60 + rank)
        for rank, c in enumerate(bm25_results, 1):
            combined[c.chunk_id] = combined.get(c.chunk_id, 0) + (1 - semantic_weight) / (60 + rank)
            
        sorted_ids = sorted(combined.keys(), key=lambda x: combined[x], reverse=True)[:top_k]
        lookup = {c.chunk_id: c for c in semantic_results + bm25_results}
        
        final = []
        for cid in sorted_ids:
            chunk = lookup[cid]
            chunk.score = combined[cid]
            final.append(chunk)
        return final

    def retrieve_with_advanced_hyde(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        llm = None,
    ) -> List[RetrievedChunk]:
        """HyDE augmented search (Hypothetical Document Embedding)."""
        if not llm:
            return self.retrieve(query, top_k, filters)
            
        try:
            prompt = f"Provide a factual summary derived from Vedic astrology regarding: {query}\n\nSummary (brief):"
            hypo_doc = llm.invoke(prompt).content
            logger.info(f"HYDE: Generated hypothetical doc ({len(hypo_doc)} chars)")
            
            hyde_emb = self.embedder.embed_texts([hypo_doc])[0]
            where = self._build_where_clause(filters) if filters else None
            
            results = self.collection.query(
                query_embeddings=[hyde_emb],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            return self._parse_results(results)
        except Exception as e:
            logger.error(f"HyDE error: {e}")
            return self.retrieve(query, top_k, filters)

    def _parse_results(self, results) -> List[RetrievedChunk]:
        chunks = []
        if results and results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                meta = results['metadatas'][0][i]
                chunks.append(RetrievedChunk(
                    chunk_id=results['ids'][0][i],
                    text=results['documents'][0][i],
                    display_text=meta.get('display_text', results['documents'][0][i]),
                    verse_sanskrit=meta.get('verse_sanskrit'),
                    score=1 - results['distances'][0][i],
                    metadata=meta
                ))
        return chunks

    def _build_where_clause(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        conditions = []
        for key, value in filters.items():
            if key in ['planets', 'houses', 'signs', 'nakshatras']:
                conditions.append({key: {"$contains": value}})
            else:
                conditions.append({key: {"$eq": value}})
        
        if not conditions: return {}
        return conditions[0] if len(conditions) == 1 else {"$and": conditions}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?")
    parser.add_argument("--hybrid", action="store_true")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    
    retriever = AstrologyRetriever()
    if args.query:
        if args.hybrid:
            results = retriever.retrieve_hybrid(args.query, top_k=args.top_k)
        else:
            results = retriever.retrieve(args.query, top_k=args.top_k)
            
        for i, res in enumerate(results, 1):
            print(f"\n--- Result {i} ---\n{res}")
