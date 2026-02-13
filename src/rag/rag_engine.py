# src\rag\rag_engine.py
#!/usr/bin/env python3
"""
RAG Engine for Astrology Chatbot - Phase 4 Enhanced

Orchestrates retrieval and generation for question-answering.

Phase 4 Enhancements:
- Persona system (hybrid traditional-modern astrologer)
- LangChain prompt templates
- Conversation storage (JSON now, MongoDB later)
- Follow-up detection and query expansion
- Preserved auto-routing logic (keyword/conceptual/general)
"""

import os
import json
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

# Phase 4: Import personas and templates
try:
    from src.llm.prompts import (
        get_persona,
        get_default_persona,
        PromptTemplateFactory,
        format_context_from_chunks,
        format_conversation_history,
    )
    PROMPTS_AVAILABLE = True
except ImportError:
    print("[WARN] Prompts module not found. Using legacy prompts.")
    PROMPTS_AVAILABLE = False

# Phase 4: Import conversation store
try:
    from conversation_store import ConversationStore, get_default_store
    STORAGE_AVAILABLE = True
except ImportError:
    print("[WARN] ConversationStore not found. History will be in-memory only.")
    STORAGE_AVAILABLE = False

from src.rag.memory_retriever import MemoryRetriever


@dataclass
class RAGResponse:
    """Container for RAG response."""
    answer: str
    sources: List[RetrievedChunk]
    query: str
    session_id: Optional[str] = None
    
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
    
    Phase 4 Enhancements:
    - Persona-driven responses
    - Conversation history storage
    - Follow-up detection
    - Context expansion
    """
    
    # Legacy system prompt (fallback if prompts module unavailable)
    LEGACY_SYSTEM_PROMPT = """You are an expert Vedic astrology consultant with deep knowledge of classical texts like Brihat Parasara Hora Shastra, Jataka Parijata, and other authoritative sources.

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
        collection_name: str = "saravali_vol1",
        db_path: str = "data/vectordb",
        llm_provider: str = "google",
        llm_model: Optional[str] = None,
        temperature: float = 0.3,
        retriever: Optional[AstrologyRetriever] = None,
        use_reranker: bool = False,
        reranker_method: str = "cross-encoder",
        persona: str = "hybrid",  # Phase 4: Persona selection
        enable_storage: bool = True,  # Phase 4: Persistent storage
        session_id: Optional[str] = None,  # Phase 4: Session management
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
            reranker_method: 'cross-encoder'
            persona: Astrologer persona ('hybrid', 'traditional', 'educational', 'western')
            enable_storage: Enable conversation storage
            session_id: Existing session ID (creates new if None)
        """
        # Initialize retriever
        self.retriever = retriever or AstrologyRetriever(
            collection_name=collection_name,
            db_path=db_path
        )
        
        self.llm = create_llm(
            provider=llm_provider,
            model=llm_model,
            temperature=temperature,
            max_tokens=4096,
            use_rate_limiting=True,
        )
        
        # Ensure retriever exists (Phase 6.2 fix)
        self.retriever = retriever or AstrologyRetriever(
            collection_name=collection_name,
            db_path=db_path,
            embedder=getattr(self, 'embedder', None)
        )
        
        # Initialize reranker if requested
        self.reranker = None
        if use_reranker:
            try:
                self.reranker = Reranker(method=reranker_method)
                print(f"[OK] Reranker enabled: {reranker_method}")
            except Exception as e:
                print(f"[WARN] Reranker initialization failed: {e}")
        
        # Phase 4: Initialize persona and templates
        if PROMPTS_AVAILABLE:
            print(f"[INFO] Loading persona: {persona}")
            self.persona_config = get_persona(persona)
            self.persona_name = persona
            
            # Create prompt templates
            factory = PromptTemplateFactory()
            self.rag_template = factory.get_rag_template(self.persona_config)
            self.intent_classifier_template = factory.get_intent_classifier_template()
            self.followup_detector_template = factory.get_followup_detector_template()
            self.context_expander_template = factory.get_context_expander_template()
            
            print(f"[OK] Persona loaded: {self.persona_config.name}")
        else:
            print(f"[WARN] Using legacy system prompt (prompts module unavailable)")
            self.persona_config = None
            self.persona_name = "legacy"

        # Initialize Long-Term Memory (Persistent ChromaDB)
        self.memory_retriever = MemoryRetriever(
            persist_directory=db_path,
            collection_name="conversation_memories"
        )
        print("[OK] Long-term memory retriever initialized (conversation_memories)")
        
        # Phase 4: Initialize conversation storage
        self.enable_storage = enable_storage and STORAGE_AVAILABLE
        self.session_id = session_id
        
        if self.enable_storage:
            self.conversation_store = get_default_store()
            
            # Create or load session
            if session_id:
                print(f"[INFO] Using existing session: {session_id}")
            else:
                self.session_id = self.conversation_store.create_session(
                    metadata={"persona": persona}
                )
                print(f"[INFO] Created new session: {self.session_id}")
        else:
            self.conversation_store = None
            print(f"[WARN] Conversation storage disabled")
        
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
        
        return queries
    
    def _classify_query_intent(self, query: str) -> str:
        """
        Classify query intent to select retrieval strategy.
        
        Uses hybrid approach: rule-based primary, LLM fallback for edge cases.
        
        Returns:
            One of: "keyword", "conceptual", "general"
        """
        q_lower = query.lower()
        
        # 1. Keyword/Citation intent -> Hybrid Search
        # Explicit request for verse/chapter numbers or Sanskrit terms
        keyword_indicators = [
            "verse", "chapter", "shloka", "sloka", "sanskrit", 
            "number", "citation", "reference", "source", "author",
            "stanza", "text says", "quote"
        ]
        if any(k in q_lower for k in keyword_indicators):
            return "keyword"
            
        # 2. Conceptual/Explanatory intent -> HyDE
        # Complex questions asking for mechanics or reasons
        conceptual_indicators = [
            "why", "how", "explain", "concept", "significance",
            "relationship", "difference", "between", "impact of",
            "reason for", "philosophy", "understand"
        ]
        # Also treat very long/detailed queries as conceptual
        if len(query.split()) > 15 or any(k in q_lower for k in conceptual_indicators):
            return "conceptual"
            
        # 3. Default -> Vector Search
        return "general"
    
    def _is_followup_query(
        self,
        query: str,
        conversation_history: List[Dict[str, str]]
    ) -> bool:
        """
        Detect if query is a follow-up to previous conversation.
        
        Uses rule-based detection (fast, accurate for most cases).
        
        Args:
            query: Current user query
            conversation_history: Previous conversation turns
            
        Returns:
            True if follow-up, False if new query
        """
        if not conversation_history:
            return False
        
        q_lower = query.lower()
        
        # Strong follow-up indicators
        strong_indicators = [
            query.startswith("what about ") and len(query.split()) < 8,  # "what about in the 7th?"
            query.startswith("what if "),
            query.startswith("and "),
            query.startswith("also "),
            "tell me more about that" in q_lower,
            "about that" in q_lower,
            "about it" in q_lower,
        ]
        
        if any(strong_indicators):
            return True
        
        # Check for pronouns without clear antecedents
        pronouns = ["it", "that", "this", "them", "they"]
        has_vague_pronoun = any(
            f" {pronoun} " in f" {q_lower} " or f" {pronoun}'" in f" {q_lower} "
            for pronoun in pronouns
        )
        
        # Short query with vague pronoun is likely follow-up
        if has_vague_pronoun and len(query.split()) < 10:
            return True
        
        return False
    
    def _expand_followup_query(
        self,
        query: str,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Expand follow-up query into self-contained query.
        
        Args:
            query: Follow-up query (e.g., "What about in the 7th?")
            conversation_history: Previous turns
            
        Returns:
            Expanded query (e.g., "What are effects of Mars in the 7th house?")
        """
        if not PROMPTS_AVAILABLE:
            return query  # Can't expand without templates
        
        # Get recent context
        context = self._get_recent_context(conversation_history, n=3)
        
        # Format prompt
        try:
            prompt = self.context_expander_template.format(
                conversation_context=context,
                followup_query=query
            )
            
            # Get expansion from LLM
            response = self.llm.invoke(prompt)
            expanded = response.content.strip()
            
            # Validate expansion (should be longer and more specific)
            if len(expanded) > len(query) and expanded != query:
                return expanded
            
        except Exception as e:
            print(f"[WARN] Query expansion failed: {e}")
        
        # Fallback: return original query
        return query
    
    def _get_recent_context(
        self,
        conversation_history: List[Dict[str, str]],
        n: int = 3
    ) -> str:
        """
        Get summary of recent conversation for context.
        
        Args:
            conversation_history: Previous turns
            n: Number of recent turns to include
            
        Returns:
            Formatted context string
        """
        if not conversation_history:
            return "No previous conversation."
        
        recent = conversation_history[-n:] if len(conversation_history) > n else conversation_history
        
        parts = []
        for turn in recent:
            if 'user' in turn:
                parts.append(f"User asked: {turn['user']}")
            if 'assistant' in turn:
                # Summarize assistant response (first 100 chars)
                response = turn['assistant']
                summary = response[:100] + "..." if len(response) > 100 else response
                parts.append(f"Assistant explained: {summary}")
        
        return "\n".join(parts)

    def answer_question(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        use_hyde: Optional[bool] = None,   # Changed to Optional
        use_hybrid: Optional[bool] = None, # Added Explicit Flag
        expand_context: bool = True,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_profile: Optional[Dict[str, Any]] = None, # Added Profile
        save_to_store: bool = True,  # Phase 4: Auto-save to storage
    ) -> RAGResponse:
        """
        Answer a question using RAG with automatic strategy routing.
        
        Args:
            query: User question
            top_k: Number of chunks to retrieve
            filters: Metadata filters
            use_hyde: Force HyDE (None = Auto)
            use_hybrid: Force Hybrid (None = Auto)
            expand_context: Expand with related chunks
            conversation_history: Previous conversation turns (if not using storage)
            save_to_store: Save turn to conversation store
            
        Returns:
            RAGResponse with answer and sources
        """
        print(f"\n[QUERY] {query}")
        
        # Phase 4: Load history from storage if enabled
        if self.enable_storage and conversation_history is None:
            conversation_history = self.conversation_store.get_history(self.session_id)
            if conversation_history:
                print(f"[STORAGE] Loaded {len(conversation_history)} previous turns")
        
        # Phase 4: Check if this is a follow-up question
        original_query = query
        if conversation_history and len(conversation_history) > 0:
            is_followup = self._is_followup_query(query, conversation_history)
            if is_followup:
                print(f"[FOLLOW-UP] Detected follow-up question")
                expanded_query = self._expand_followup_query(query, conversation_history)
                if expanded_query and expanded_query != query:
                    print(f"[EXPANSION] '{query}' -> '{expanded_query}'")
                    query = expanded_query
        
        # Helper to determine strategy
        intent = self._classify_query_intent(query)
        
        # Resolve strategy flags (Explicit overrides Auto)
        final_hyde = use_hyde if use_hyde is not None else (intent == "conceptual")
        final_hybrid = use_hybrid if use_hybrid is not None else (intent == "keyword")
        
        # Phase 5: Retrieve Long-Term Memories (semantic search over old sessions)
        long_term_memory = ""
        if user_profile and user_profile.get('user_id'):
            user_id = user_profile['user_id']
            memories = self.memory_retriever.retrieve_memories(user_id, query, k=2)
            if memories:
                print(f"[MEMORY] Found {len(memories)} relevant past interactions")
                long_term_memory = "\n".join([f"- {m['content']}" for m in memories])

        # Log strategy decision
        strategy_name = "Custom Override"
        if use_hyde is None and use_hybrid is None:
            strategy_name = f"Auto-Router ({intent})"
        
        print(f"[ROUTER] Strategy: {strategy_name}")
        print(f"         Thinking: HyDE={final_hyde}, Hybrid={final_hybrid}, Vector={not (final_hyde or final_hybrid)}")
        
        # Expand query for better recall
        query_variations = self._expand_query(query)
        
        # Retrieve relevant chunks
        all_chunks = []
        for q in query_variations:
            if final_hyde:
                chunks = self.retriever.retrieve_with_advanced_hyde(q, top_k=top_k, filters=filters, llm=self.llm, language=language)
            elif final_hybrid:
                chunks = self.retriever.retrieve_hybrid(q, top_k=top_k, filters=filters, language=language)
            else:
                chunks = self.retriever.retrieve(q, top_k=top_k, filters=filters, language=language)
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
        
        # Build prompt (inject long-term memory here)
        prompt = self._build_prompt(query, chunks, conversation_history, user_profile, long_term_memory=long_term_memory)
        
        # Generate answer
        print(f"[GENERATION] Generating answer...")
        try:
            response = self.llm.invoke(prompt)
            answer = response.content
        except Exception as e:
            print(f"[ERROR] Generation failed: {e}")
            answer = f"I apologize, but I encountered an error generating the answer: {e}"
        
        # Phase 4: Save to conversation store
        if self.enable_storage and save_to_store:
            try:
                self.conversation_store.add_turn(
                    self.session_id,
                    original_query,  # Save original query, not expanded
                    answer
                )
                print(f"[STORAGE] Saved turn to session {self.session_id}")
            except Exception as e:
                print(f"[WARN] Failed to save turn: {e}")
        
        return RAGResponse(
            answer=answer,
            sources=chunks[:top_k],  # Return only top-k for citation
            query=original_query,
            session_id=self.session_id if self.enable_storage else None,
        )
    
    def _build_prompt(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_profile: Optional[Dict[str, Any]] = None,
        long_term_memory: str = "" # Added field
    ):
        """
        Build prompt for LLM using templates.
        
        Args:
            query: User question
            chunks: Retrieved chunks
            conversation_history: Previous turns
            
        Returns:
            Formatted messages for LLM (or string for legacy mode)
        """
        # Phase 4: Use template-based prompt if available
        if PROMPTS_AVAILABLE and self.persona_config:
            # Format context from retrieved chunks
            context = format_context_from_chunks(chunks)
            
            # Inject long-term memory into context if present
            if long_term_memory:
                context = f"--- LONG-TERM MEMORIES (FROM PAST SESSIONS) ---\n{long_term_memory}\n\n{context}"
            
            # Format conversation history (keep last 10 turns)
            chat_history = []
            if conversation_history:
                recent_history = conversation_history[-10:]  # Truncate to last 10
                chat_history = format_conversation_history(recent_history)
            
            # Generate prompt using template
            messages = self.rag_template.format_messages(
                context=context,
                chat_history=chat_history,
                question=query
            )
            
            # Inject User Profile if available
            if user_profile:
                from langchain_core.messages import SystemMessage
                profile_text = (
                    f"USER PROFILE:\n"
                    f"Name: {user_profile.get('name', 'Unknown')}\n"
                    f"User ID: {user_profile.get('user_id', 'Unknown')}\n"
                )
                if 'birth_details' in user_profile:
                    bd = user_profile['birth_details']
                    profile_text += (
                        f"Birth Date: {bd.get('date')}\n"
                        f"Birth Time: {bd.get('time')}\n"
                        f"Location: {bd.get('location', {}).get('address', 'Unknown')}\n"
                    )
                
                # Insert after system behavior prompt (index 1) but before context
                messages.insert(1, SystemMessage(content=profile_text))
            
            return messages
        
        # Legacy: Build string-based prompt (fallback)
        else:
            return self._build_legacy_prompt(query, chunks, conversation_history)
    
    def _build_legacy_prompt(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Build legacy string-based prompt (fallback if templates unavailable).
        
        Args:
            query: User question
            chunks: Retrieved chunks
            conversation_history: Previous turns
            
        Returns:
            Formatted prompt string
        """
        parts = []
        
        # System prompt
        parts.append(self.LEGACY_SYSTEM_PROMPT)
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
    
    # Phase 4: Session management methods
    
    def get_session_history(self, max_turns: Optional[int] = None) -> List[Dict[str, str]]:
        """Get conversation history for current session."""
        if not self.enable_storage:
            return []
        return self.conversation_store.get_history(self.session_id, max_turns)
    
    def clear_session_history(self):
        """Clear conversation history for current session."""
        if self.enable_storage:
            self.conversation_store.delete_session(self.session_id)
            # Create new session
            self.session_id = self.conversation_store.create_session(
                metadata={"persona": self.persona_name}
            )
            print(f"[INFO] Created new session: {self.session_id}")
    
    def switch_persona(self, persona: str):
        """Switch to a different astrologer persona."""
        if not PROMPTS_AVAILABLE:
            print("[ERROR] Cannot switch persona - prompts module unavailable")
            return
        
        print(f"[INFO] Switching persona: {self.persona_name} -> {persona}")
        self.persona_config = get_persona(persona)
        self.persona_name = persona
        
        # Recreate RAG template with new persona
        factory = PromptTemplateFactory()
        self.rag_template = factory.get_rag_template(self.persona_config)
        
        print(f"[OK] Persona switched to: {self.persona_config.name}")


def main():
    """CLI for testing RAG engine."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test RAG Engine")
    parser.add_argument("query", nargs="?", help="Question to ask")
    parser.add_argument("--collection", default="brihat_parasara_hora_sastra", help="Collection name")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve")
    parser.add_argument("--model", default="gemini-2.5-flash", help="LLM model")
    parser.add_argument("--persona", default="hybrid", help="Astrologer persona")
    parser.add_argument("--hyde", action="store_true", help="Use HyDE retrieval")
    parser.add_argument("--no-expand", action="store_true", help="Don't expand context")
    parser.add_argument("--rerank", action="store_true", help="Enable reranking")
    parser.add_argument("--reranker-method", default="cross-encoder", help="Reranker method")
    parser.add_argument("--filter-planet", help="Filter by planet")
    parser.add_argument("--filter-house", help="Filter by house")
    parser.add_argument("--no-storage", action="store_true", help="Disable conversation storage")
    
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
        persona=args.persona,
        use_reranker=args.rerank,
        reranker_method=args.reranker_method,
        enable_storage=not args.no_storage,
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
    
    if response.session_id:
        print(f"\n[INFO] Session ID: {response.session_id}")


if __name__ == "__main__":
    main()