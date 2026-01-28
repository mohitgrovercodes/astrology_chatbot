#!/usr/bin/env python3
"""
RAG Engine for Astrology Chatbot

Orchestrates retrieval and generation for question-answering.
"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Import retriever and LLM factory
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.rag.retriever import AstrologyRetriever, RetrievedChunk
from src.llm.factory import create_llm
from src.rag.reranker import Reranker


@dataclass
class RAGResponse:
    """Container for RAG response."""
    answer: str
    sources: List[RetrievedChunk]
    query: str
    
    def format_with_sources(self) -> str:
        """Format answer with source citations."""
        lines = [self.answer]
        
        if self.sources:
            lines.append("\n" + "=" * 60)
            lines.append("SOURCES")
            lines.append("=" * 60)
            
            for i, chunk in enumerate(self.sources, 1):
                lines.append(f"\n[{i}] {chunk.metadata.get('source_book', 'Unknown')}")
                if chunk.metadata.get('chapter'):
                    lines.append(f"    Chapter: {chunk.metadata['chapter']}")
                if chunk.metadata.get('verse_number'):
                    lines.append(f"    Verse: {chunk.metadata['verse_number']}")
                lines.append(f"    Relevance: {chunk.score:.2%}")
        
        return "\n".join(lines)


class RAGEngine:
    """
    RAG Engine for Astrology Q&A.
    Combines retrieval with LLM generation.
    """
    
    # System prompt for astrology expertise
    SYSTEM_PROMPT = """You are an expert Vedic astrology consultant with deep knowledge of classical texts like Brihat Parasara Hora Shastra, Jataka Parijata, and other authoritative sources.

Your role is to provide accurate, insightful answers to astrology questions based on the retrieved context from classical texts. 

Guidelines:
1. Base your answers primarily on the provided context
2. Cite specific verses or chapters when relevant
3. Explain concepts clearly for both beginners and advanced students
4. If the context doesn't fully answer the question, acknowledge limitations
5. Maintain traditional interpretations while being accessible
6. Use Sanskrit terms when appropriate, with explanations

Always be respectful of the sacred nature of Vedic astrology."""

    def __init__(
        self,
        collection_name: str = "brihat_parasara_hora_sastra",
        db_path: str = "data/vectordb",
        llm_provider: str = "google",
        llm_model: Optional[str] = None,
        temperature: float = 0.3,
        retriever: Optional[AstrologyRetriever] = None,
        use_reranker: bool = False,
        reranker_method: str = "cohere",
    ):
        """
        Initialize RAG engine.
        
        Args:
            collection_name: ChromaDB collection name
            db_path: Path to vector database
            llm_provider: 'google' or 'openai'
            llm_model: LLM model name (auto-selected if None)
            temperature: LLM temperature
            retriever: Optional pre-initialized retriever
            use_reranker: Enable reranking for better precision
            reranker_method: 'cohere' or 'cross-encoder'
        """
        # Initialize retriever
        self.retriever = retriever or AstrologyRetriever(
            collection_name=collection_name,
            db_path=db_path
        )
        
        # Initialize LLM
        print(f"[INFO] Initializing LLM: {llm_provider}/{llm_model or 'default'}")
        self.llm = create_llm(
            provider=llm_provider,
            model=llm_model,
            temperature=temperature,
            max_tokens=2048,
            use_rate_limiting=True,
        )
        
        # Initialize reranker if requested
        self.reranker = None
        if use_reranker:
            try:
                self.reranker = Reranker(method=reranker_method)
                print(f"[OK] Reranker enabled: {reranker_method}")
            except Exception as e:
                print(f"[WARN] Reranker initialization failed: {e}")
        
        print(f"[OK] RAG Engine ready")
    
    def _expand_query(self, query: str) -> List[str]:
        """
        Expand query into multiple variations for better retrieval.
        
        Args:
            query: Original user query
            
        Returns:
            List of query variations (including original)
        """
        queries = [query]
        
        # Simple synonym expansion for common astrological terms
        synonyms = {
            "house": ["bhava"],
            "planet": ["graha"],
            "sign": ["rashi", "zodiac sign"],
            "effect": ["result", "signification", "indication"],
            "mars": ["mangal", "kuja"],
            "jupiter": ["guru", "brihaspati"],
            "saturn": ["shani"],
            "venus": ["shukra"],
            "mercury": ["budha"],
        }
        
        query_lower = query.lower()
        for term, syns in synonyms.items():
            if term in query_lower:
                for syn in syns[:1]:  # Use first synonym only
                    expanded = query.lower().replace(term, syn)
                    if expanded != query.lower():
                        queries.append(expanded)
                        break
        
        return queries[:3]  # Max 3 query variations
    
    def answer_question(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        use_hyde: bool = False,
        expand_context: bool = True,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> RAGResponse:
        """
        Answer a question using RAG.
        
        Args:
            query: User question
            top_k: Number of chunks to retrieve
            filters: Metadata filters
            use_hyde: Use HyDE retrieval
            expand_context: Expand with related chunks
            conversation_history: Previous conversation turns
            
        Returns:
            RAGResponse with answer and sources
        """
        print(f"\n[QUERY] {query}")
        
        # Expand query for better recall
        query_variations = self._expand_query(query)
        if len(query_variations) > 1:
            print(f"[EXPANSION] Generated {len(query_variations)} query variations")
        
        # Retrieve relevant chunks using hybrid search
        all_chunks = []
        for q in query_variations:
            if use_hyde:
                chunks = self.retriever.retrieve_with_hyde(q, top_k=top_k, filters=filters)
            else:
                # Use hybrid search by default for better quality
                chunks = self.retriever.retrieve_hybrid(q, top_k=top_k, filters=filters)
            all_chunks.extend(chunks)
        
        # Deduplicate and sort by score
        seen_ids = set()
        unique_chunks = []
        for chunk in sorted(all_chunks, key=lambda x: x.score, reverse=True):
            if chunk.chunk_id not in seen_ids:
                seen_ids.add(chunk.chunk_id)
                unique_chunks.append(chunk)
                if len(unique_chunks) >= top_k:
                    break
        
        chunks = unique_chunks
        print(f"[RETRIEVAL] Found {len(chunks)} unique chunks")
        
        # Rerank if enabled
        if self.reranker and len(chunks) > 1:
            chunks = self.reranker.rerank(query, chunks, top_k=top_k)
        
        # Expand context
        if expand_context and chunks:
            chunks = self.retriever.expand_context(chunks, max_related=2)
            print(f"[CONTEXT] Expanded to {len(chunks)} chunks")
        
        # Build prompt
        prompt = self._build_prompt(query, chunks, conversation_history)
        
        # Generate answer
        print(f"[GENERATION] Generating answer...")
        try:
            response = self.llm.invoke(prompt)
            answer = response.content
        except Exception as e:
            print(f"[ERROR] Generation failed: {e}")
            answer = f"I apologize, but I encountered an error generating the answer: {e}"
        
        return RAGResponse(
            answer=answer,
            sources=chunks[:top_k],  # Return only top-k for citation
            query=query,
        )
    
    def _build_prompt(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Build prompt for LLM.
        
        Args:
            query: User question
            chunks: Retrieved chunks
            conversation_history: Previous turns
            
        Returns:
            Formatted prompt string
        """
        parts = []
        
        # System prompt
        parts.append(self.SYSTEM_PROMPT)
        parts.append("\n" + "=" * 60 + "\n")
        
        # Context from retrieved chunks
        if chunks:
            parts.append("CONTEXT FROM CLASSICAL TEXTS:\n")
            for i, chunk in enumerate(chunks, 1):
                parts.append(f"\n[Source {i}]")
                parts.append(f"Book: {chunk.metadata.get('source_book', 'Unknown')}")
                if chunk.metadata.get('chapter'):
                    parts.append(f"Chapter: {chunk.metadata['chapter']}")
                if chunk.metadata.get('verse_number'):
                    parts.append(f"Verse: {chunk.metadata['verse_number']}")
                parts.append(f"\n{chunk.display_text}\n")
                
                if chunk.verse_sanskrit:
                    parts.append(f"Sanskrit: {chunk.verse_sanskrit}\n")
        else:
            parts.append("No relevant context found in the database.\n")
        
        parts.append("\n" + "=" * 60 + "\n")
        
        # Conversation history
        if conversation_history:
            parts.append("CONVERSATION HISTORY:\n")
            for turn in conversation_history[-3:]:  # Last 3 turns
                parts.append(f"User: {turn.get('user', '')}")
                parts.append(f"Assistant: {turn.get('assistant', '')}\n")
            parts.append("\n")
        
        # Current question
        parts.append(f"QUESTION: {query}\n")
        parts.append("\nPlease provide a comprehensive answer based on the context above. ")
        parts.append("Cite specific sources when relevant (e.g., 'According to Source 1...').")
        
        return "\n".join(parts)
    
    def _format_sources(self, chunks: List[RetrievedChunk]) -> str:
        """Format source citations."""
        if not chunks:
            return "No sources available."
        
        lines = []
        for i, chunk in enumerate(chunks, 1):
            source = f"[{i}] {chunk.metadata.get('source_book', 'Unknown')}"
            if chunk.metadata.get('chapter'):
                source += f" - {chunk.metadata['chapter']}"
            if chunk.metadata.get('verse_number'):
                source += f" (Verse {chunk.metadata['verse_number']})"
            source += f" - Relevance: {chunk.score:.2%}"
            lines.append(source)
        
        return "\n".join(lines)


def main():
    """CLI for testing RAG engine."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test RAG Engine")
    parser.add_argument("query", nargs="?", help="Question to ask")
    parser.add_argument("--collection", default="brihat_parasara_hora_sastra", help="Collection name")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve")
    parser.add_argument("--model", default="gemini-2.0-flash-exp", help="LLM model")
    parser.add_argument("--hyde", action="store_true", help="Use HyDE retrieval")
    parser.add_argument("--no-expand", action="store_true", help="Don't expand context")
    parser.add_argument("--rerank", action="store_true", help="Enable reranking")
    parser.add_argument("--reranker-method", default="cohere", choices=["cohere", "cross-encoder"], help="Reranker method")
    parser.add_argument("--filter-planet", help="Filter by planet")
    parser.add_argument("--filter-house", help="Filter by house")
    
    args = parser.parse_args()
    
    if not args.query:
        parser.print_help()
        print("\n[ERROR] query argument required")
        return
    
    # Build filters
    filters = {}
    if args.filter_planet:
        filters["planets"] = args.filter_planet
    if args.filter_house:
        filters["houses"] = args.filter_house
    
    # Initialize engine
    engine = RAGEngine(
        collection_name=args.collection,
        llm_model=args.model,
        use_reranker=args.rerank,
        reranker_method=args.reranker_method,
    )
    
    # Get answer
    response = engine.answer_question(
        query=args.query,
        top_k=args.top_k,
        filters=filters,
        use_hyde=args.hyde,
        expand_context=not args.no_expand,
    )
    
    # Display
    print("\n" + "=" * 60)
    print("ANSWER")
    print("=" * 60)
    print(response.format_with_sources())


if __name__ == "__main__":
    main()
