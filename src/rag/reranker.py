#!/usr/bin/env python3
"""
Reranker for improving retrieval precision.

Uses cross-encoder models or API-based reranking (Cohere).
"""

import os
from typing import List, Optional
from dataclasses import dataclass

# Add project root to path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.rag.retriever import RetrievedChunk


class Reranker:
    """
    Reranker for improving retrieval precision.
    Supports both local cross-encoder and Cohere Rerank API.
    """
    
    def __init__(
        self,
        method: str = "cohere",  # "cohere" or "cross-encoder"
        model: str = "rerank-english-v3.0",
    ):
        """
        Initialize reranker.
        
        Args:
            method: Reranking method ("cohere" or "cross-encoder")
            model: Model name
        """
        self.method = method
        self.model = model
        self.client = None
        
        if method == "cohere":
            self._init_cohere()
        elif method == "cross-encoder":
            self._init_cross_encoder()
        else:
            raise ValueError(f"Unknown reranking method: {method}")
    
    def _init_cohere(self):
        """Initialize Cohere client."""
        try:
            import cohere
            api_key = os.environ.get("COHERE_API_KEY")
            if api_key:
                self.client = cohere.Client(api_key)
                print(f"[OK] Cohere reranker initialized")
            else:
                print("[WARN] COHERE_API_KEY not set. Reranking disabled.")
        except ImportError:
            print("[WARN] Cohere not installed. Install: pip install cohere")
    
    def _init_cross_encoder(self):
        """Initialize cross-encoder model."""
        try:
            from sentence_transformers import CrossEncoder
            self.client = CrossEncoder(self.model)
            print(f"[OK] Cross-encoder initialized: {self.model}")
        except ImportError:
            print("[WARN] sentence-transformers not installed. Install: pip install sentence-transformers")
    
    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: Optional[int] = None,
    ) -> List[RetrievedChunk]:
        """
        Rerank retrieved chunks.
        
        Args:
            query: User query
            chunks: Retrieved chunks to rerank
            top_k: Number of top results to return (None = all)
            
        Returns:
            Reranked chunks
        """
        if not self.client or not chunks:
            return chunks
        
        if self.method == "cohere":
            return self._rerank_cohere(query, chunks, top_k)
        elif self.method == "cross-encoder":
            return self._rerank_cross_encoder(query, chunks, top_k)
        
        return chunks
    
    def _rerank_cohere(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: Optional[int],
    ) -> List[RetrievedChunk]:
        """Rerank using Cohere API."""
        try:
            # Prepare documents
            documents = [chunk.display_text for chunk in chunks]
            
            # Rerank
            response = self.client.rerank(
                query=query,
                documents=documents,
                model=self.model,
                top_n=top_k or len(chunks),
            )
            
            # Reorder chunks based on rerank results
            reranked = []
            for result in response.results:
                idx = result.index
                chunk = chunks[idx]
                # Update score with rerank score
                chunk.score = result.relevance_score
                reranked.append(chunk)
            
            print(f"[RERANK] Cohere reranked {len(reranked)} chunks")
            return reranked
            
        except Exception as e:
            print(f"[ERROR] Cohere reranking failed: {e}")
            return chunks
    
    def _rerank_cross_encoder(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: Optional[int],
    ) -> List[RetrievedChunk]:
        """Rerank using local cross-encoder."""
        try:
            # Prepare query-document pairs
            pairs = [[query, chunk.display_text] for chunk in chunks]
            
            # Get scores
            scores = self.client.predict(pairs)
            
            # Update chunk scores and sort
            for chunk, score in zip(chunks, scores):
                chunk.score = float(score)
            
            reranked = sorted(chunks, key=lambda x: x.score, reverse=True)
            
            if top_k:
                reranked = reranked[:top_k]
            
            print(f"[RERANK] Cross-encoder reranked {len(reranked)} chunks")
            return reranked
            
        except Exception as e:
            print(f"[ERROR] Cross-encoder reranking failed: {e}")
            return chunks


def main():
    """CLI for testing reranker."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Reranker")
    parser.add_argument("--method", default="cohere", choices=["cohere", "cross-encoder"])
    parser.add_argument("--model", help="Model name")
    
    args = parser.parse_args()
    
    # Test reranker initialization
    reranker = Reranker(method=args.method, model=args.model or "rerank-english-v3.0")
    
    print(f"\n✅ Reranker initialized: {args.method}")
    print(f"Model: {reranker.model}")
    print(f"Client available: {reranker.client is not None}")


if __name__ == "__main__":
    main()
