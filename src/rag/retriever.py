#!/usr/bin/env python3
"""
RAG Retriever for Astrology Chatbot

Semantic search with ChromaDB, metadata filtering, and HyDE retrieval.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
import numpy as np

# Import embedder for query embedding
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.rag.preprocessing.embedder import Embedder


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
    Retriever for astrology RAG system.
    Supports semantic search, metadata filtering, and HyDE retrieval.
    """
    
    def __init__(
        self,
        collection_name: str = "brihat_parasara_hora_sastra",
        db_path: str = "data/vectordb",
        embedder: Optional[Embedder] = None,
    ):
        """
        Initialize retriever.
        
        Args:
            collection_name: ChromaDB collection name
            db_path: Path to ChromaDB storage
            embedder: Embedder instance (creates new if None)
        """
        self.collection_name = collection_name
        self.db_path = Path(db_path)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get collection
        try:
            self.collection = self.client.get_collection(name=collection_name)
            print(f"[OK] Loaded collection: {collection_name}")
            print(f"[INFO] Collection size: {self.collection.count()} chunks")
        except Exception as e:
            raise ValueError(f"Collection '{collection_name}' not found. Error: {e}")
        
        # Initialize embedder
        self.embedder = embedder or Embedder()
        if not self.embedder.client:
            print("[WARN] No OpenAI API key. Retrieval will not work.")
        
        # Initialize BM25 index for hybrid search
        self.bm25_index = None
        self.bm25_documents = []
        self.bm25_ids = []
        self._build_bm25_index()
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """
        Retrieve relevant chunks using semantic search.
        
        Args:
            query: User question
            top_k: Number of chunks to retrieve
            filters: Metadata filters (e.g., {"planets": "Mars", "houses": "5"})
            
        Returns:
            List of RetrievedChunk objects
        """
        if not self.embedder.client:
            print("[ERROR] Cannot retrieve without embedder")
            return []
        
        # Embed query
        query_embedding = self.embedder.embed_texts([query])[0]
        
        # Build where clause for metadata filtering
        where_clause = self._build_where_clause(filters) if filters else None
        
        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause,
            include=["documents", "metadatas", "distances"]
        )
        
        # Convert to RetrievedChunk objects
        chunks = []
        if results and results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                chunk_id = results['ids'][0][i]
                document = results['documents'][0][i]
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i]
                
                # Convert distance to similarity score (cosine distance -> similarity)
                score = 1 - distance
                
                chunks.append(RetrievedChunk(
                    chunk_id=chunk_id,
                    text=document,
                    display_text=metadata.get('display_text', document),
                    verse_sanskrit=metadata.get('verse_sanskrit'),
                    score=score,
                    metadata=metadata,
                ))
        
        return chunks
    
    def _build_bm25_index(self):
        """Build BM25 index for keyword search."""
        try:
            # Get all documents from collection
            all_docs = self.collection.get(include=["documents", "metadatas"])
            
            if all_docs and all_docs['documents']:
                self.bm25_documents = all_docs['documents']
                self.bm25_ids = all_docs['ids']
                
                # Tokenize documents (simple whitespace tokenization)
                tokenized_docs = [doc.lower().split() for doc in self.bm25_documents]
                
                # Build BM25 index
                self.bm25_index = BM25Okapi(tokenized_docs)
                print(f"[OK] Built BM25 index with {len(self.bm25_documents)} documents")
        except Exception as e:
            print(f"[WARN] Failed to build BM25 index: {e}")
    
    def retrieve_hybrid(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        semantic_weight: float = 0.7,
    ) -> List[RetrievedChunk]:
        """
        Hybrid retrieval combining semantic and keyword (BM25) search.
        
        Args:
            query: User question
            top_k: Number of chunks to retrieve
            filters: Metadata filters
            semantic_weight: Weight for semantic search (1-semantic_weight for BM25)
            
        Returns:
            List of RetrievedChunk objects
        """
        # Get semantic results
        semantic_results = self.retrieve(query, top_k=top_k * 2, filters=filters)
        
        # Get BM25 results if index is available
        bm25_results = []
        if self.bm25_index:
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25_index.get_scores(tokenized_query)
            
            # Get top-k BM25 results
            top_indices = np.argsort(bm25_scores)[::-1][:top_k * 2]
            
            for idx in top_indices:
                if bm25_scores[idx] > 0:  # Only include non-zero scores
                    chunk_id = self.bm25_ids[idx]
                    # Get full chunk data
                    result = self.collection.get(
                        ids=[chunk_id],
                        include=["documents", "metadatas"]
                    )
                    if result and result['ids']:
                        metadata = result['metadatas'][0]
                        bm25_results.append(RetrievedChunk(
                            chunk_id=chunk_id,
                            text=result['documents'][0],
                            display_text=metadata.get('display_text', result['documents'][0]),
                            verse_sanskrit=metadata.get('verse_sanskrit'),
                            score=float(bm25_scores[idx]),
                            metadata=metadata,
                        ))
        
        # Combine using Reciprocal Rank Fusion (RRF)
        combined_scores = {}
        k = 60  # RRF constant
        
        # Add semantic scores
        for rank, chunk in enumerate(semantic_results, 1):
            combined_scores[chunk.chunk_id] = combined_scores.get(chunk.chunk_id, 0) + \
                semantic_weight / (k + rank)
        
        # Add BM25 scores
        for rank, chunk in enumerate(bm25_results, 1):
            combined_scores[chunk.chunk_id] = combined_scores.get(chunk.chunk_id, 0) + \
                (1 - semantic_weight) / (k + rank)
        
        # Sort by combined score and get top-k
        sorted_ids = sorted(combined_scores.keys(), key=lambda x: combined_scores[x], reverse=True)[:top_k]
        
        # Build final results
        final_results = []
        all_chunks = {c.chunk_id: c for c in semantic_results + bm25_results}
        
        for chunk_id in sorted_ids:
            if chunk_id in all_chunks:
                chunk = all_chunks[chunk_id]
                # Update score to combined score
                chunk.score = combined_scores[chunk_id]
                final_results.append(chunk)
        
        return final_results
    
    def retrieve_with_advanced_hyde(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        llm = None,
    ) -> List[RetrievedChunk]:
        """
        Advanced HyDE retrieval with hypothetical document generation.
        
        Uses LLM to generate a hypothetical answer, then searches for
        chunks similar to that answer.
        
        Args:
            query: User question
            top_k: Number of chunks to retrieve
            filters: Metadata filters
            llm: Optional LLM for generating hypothetical documents
            
        Returns:
            List of RetrievedChunk objects
        """
        if not llm:
            # Fall back to standard HyDE
            return self.retrieve_with_hyde(query, top_k, filters)
        
        try:
            # Generate hypothetical answer
            hyde_prompt = f"""Generate a brief, factual answer to this astrology question based on classical Vedic texts:

Question: {query}

Answer (2-3 sentences):"""
            
            response = llm.invoke(hyde_prompt)
            hypothetical_doc = response.content
            
            print(f"[HYDE] Generated hypothetical document ({len(hypothetical_doc)} chars)")
            
            # Embed hypothetical document
            hyde_embedding = self.embedder.embed_texts([hypothetical_doc])[0]
            
            # Search using hypothetical document embedding
            where_clause = self._build_where_clause(filters) if filters else None
            
            results = self.collection.query(
                query_embeddings=[hyde_embedding],
                n_results=top_k,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            # Convert to RetrievedChunk objects
            chunks = []
            if results and results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    chunk_id = results['ids'][0][i]
                    document = results['documents'][0][i]
                    metadata = results['metadatas'][0][i]
                    distance = results['distances'][0][i]
                    score = 1 - distance
                    
                    chunks.append(RetrievedChunk(
                        chunk_id=chunk_id,
                        text=document,
                        display_text=metadata.get('display_text', document),
                        verse_sanskrit=metadata.get('verse_sanskrit'),
                        score=score,
                        metadata=metadata,
                    ))
            
            return chunks
            
        except Exception as e:
            print(f"[ERROR] Advanced HyDE failed: {e}")
            # Fall back to standard retrieval
            return self.retrieve(query, top_k, filters)
    
    def retrieve_with_hyde(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """
        HyDE-enhanced retrieval using hypothetical questions.
        
        Searches both the query and stored hypothetical questions,
        then deduplicates and ranks results.
        
        Args:
            query: User question
            top_k: Number of chunks to retrieve
            filters: Metadata filters
            
        Returns:
            List of RetrievedChunk objects
        """
        # Standard semantic search
        semantic_results = self.retrieve(query, top_k=top_k * 2, filters=filters)
        
        # TODO: Could also search hypothetical_questions field if stored separately
        # For now, standard retrieval should match well since hypothetical questions
        # are embedded in the text_for_embedding field
        
        # Deduplicate and take top_k
        seen_ids = set()
        unique_results = []
        for chunk in semantic_results:
            if chunk.chunk_id not in seen_ids:
                seen_ids.add(chunk.chunk_id)
                unique_results.append(chunk)
                if len(unique_results) >= top_k:
                    break
        
        return unique_results
    
    def expand_context(
        self,
        chunks: List[RetrievedChunk],
        max_related: int = 2,
    ) -> List[RetrievedChunk]:
        """
        Expand context by fetching related chunks.
        
        Args:
            chunks: Initial retrieved chunks
            max_related: Max related chunks to fetch per chunk
            
        Returns:
            Expanded list of chunks (original + related)
        """
        expanded = list(chunks)
        seen_ids = {c.chunk_id for c in chunks}
        
        for chunk in chunks:
            # Get related chunk IDs from metadata
            related_ids_str = chunk.metadata.get('related_chunks', '')
            if not related_ids_str:
                continue
            
            # Parse related IDs (stored as comma-separated or JSON)
            try:
                if related_ids_str.startswith('['):
                    related_ids = json.loads(related_ids_str)
                else:
                    related_ids = related_ids_str.split(',')
            except:
                continue
            
            # Fetch related chunks
            for related_id in related_ids[:max_related]:
                related_id = related_id.strip()
                if related_id and related_id not in seen_ids:
                    try:
                        result = self.collection.get(
                            ids=[related_id],
                            include=["documents", "metadatas"]
                        )
                        
                        if result and result['ids']:
                            metadata = result['metadatas'][0]
                            expanded.append(RetrievedChunk(
                                chunk_id=related_id,
                                text=result['documents'][0],
                                display_text=metadata.get('display_text', result['documents'][0]),
                                verse_sanskrit=metadata.get('verse_sanskrit'),
                                score=chunk.score * 0.8,  # Lower score for related
                                metadata=metadata,
                            ))
                            seen_ids.add(related_id)
                    except:
                        continue
        
        return expanded
    
    def _build_where_clause(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build ChromaDB where clause from filters.
        
        Args:
            filters: Dict like {"planets": "Mars", "houses": "5"}
            
        Returns:
            ChromaDB where clause
        """
        conditions = []
        
        for key, value in filters.items():
            if key in ['planets', 'houses', 'signs', 'nakshatras', 'yogas', 'concepts']:
                # These are stored as comma-separated strings
                # Use $contains for substring match
                conditions.append({key: {"$contains": value}})
            elif key in ['source_book', 'chapter', 'section', 'tradition', 'verse_number']:
                # Exact match
                conditions.append({key: {"$eq": value}})
            elif key == 'has_verse':
                # Boolean
                conditions.append({key: {"$eq": bool(value)}})
        
        if not conditions:
            return {}
        
        if len(conditions) == 1:
            return conditions[0]
        
        # Multiple conditions: AND
        return {"$and": conditions}
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection."""
        count = self.collection.count()
        
        # Sample metadata
        sample = self.collection.get(limit=min(50, count), include=["metadatas"])
        
        info = {
            "collection_name": self.collection_name,
            "total_chunks": count,
            "db_path": str(self.db_path),
        }
        
        if sample and sample.get("metadatas"):
            metadatas = sample["metadatas"]
            info["sample_books"] = list(set(m.get("source_book") for m in metadatas if m.get("source_book")))[:5]
            info["sample_chapters"] = list(set(m.get("chapter") for m in metadatas if m.get("chapter")))[:5]
        
        return info


def main():
    """CLI for testing retriever."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test RAG Retriever")
    parser.add_argument("query", nargs="?", help="Query to search")
    parser.add_argument("--collection", default="brihat_parasara_hora_sastra", help="Collection name")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results")
    parser.add_argument("--filter-planet", help="Filter by planet (e.g., Mars)")
    parser.add_argument("--filter-house", help="Filter by house (e.g., 5)")
    parser.add_argument("--hyde", action="store_true", help="Use HyDE retrieval")
    parser.add_argument("--hybrid", action="store_true", help="Use hybrid search (semantic + BM25)")
    parser.add_argument("--expand", action="store_true", help="Expand context with related chunks")
    parser.add_argument("--info", action="store_true", help="Show collection info")
    
    args = parser.parse_args()
    
    # Initialize retriever
    retriever = AstrologyRetriever(collection_name=args.collection)
    
    # Show info mode
    if args.info:
        info = retriever.get_collection_info()
        print("\n" + "=" * 60)
        print("COLLECTION INFO")
        print("=" * 60)
        for key, value in info.items():
            print(f"{key}: {value}")
        return
    
    # Query mode
    if not args.query:
        parser.print_help()
        print("\n[ERROR] query argument required (or use --info)")
        return
    
    # Build filters
    filters = {}
    if args.filter_planet:
        filters["planets"] = args.filter_planet
    if args.filter_house:
        filters["houses"] = args.filter_house
    
    # Retrieve
    print(f"\n[QUERY] {args.query}")
    if filters:
        print(f"[FILTERS] {filters}")
    print()
    
    if args.hybrid:
        chunks = retriever.retrieve_hybrid(args.query, top_k=args.top_k, filters=filters)
    elif args.hyde:
        chunks = retriever.retrieve_with_hyde(args.query, top_k=args.top_k, filters=filters)
    else:
        chunks = retriever.retrieve(args.query, top_k=args.top_k, filters=filters)
    
    # Expand context
    if args.expand:
        chunks = retriever.expand_context(chunks)
    
    # Display results
    print("=" * 60)
    print(f"RETRIEVED {len(chunks)} CHUNKS")
    print("=" * 60)
    
    for i, chunk in enumerate(chunks, 1):
        print(f"\n--- Chunk {i} ---")
        print(chunk)
        print()


if __name__ == "__main__":
    main()
