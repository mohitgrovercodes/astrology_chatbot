# config/rag_config.py
"""
Centralized RAG Configuration
Single source of truth for all RAG retrieval parameters

Location: config/rag_config.py (project root level)

UPDATED: Added reranking and context expansion configuration
"""


class RAGConfig:
    """Centralized RAG retrieval configuration - EDIT HERE ONLY"""
    
    # ============================================
    # TOP_K SETTINGS - CHANGE ONLY HERE!
    # ============================================
    
    # Default retrieval (general queries)
    DEFAULT_TOP_K = 10  # Changed from 5 -> 10 [OK]
    
    # By content type (for validation-aware retrieval)
    VALIDATION_RULES_TOP_K = 15  # More rules = better coverage
    INTERPRETATIONS_TOP_K = 10   # Balanced
    GENERAL_KNOWLEDGE_TOP_K = 8  # Moderate
    CHITCHAT_TOP_K = 3          # Fast, focused
    
    # By query complexity
    SIMPLE_QUERY_TOP_K = 5       # Quick answers
    STANDARD_QUERY_TOP_K = 10    # Normal predictions
    COMPLEX_QUERY_TOP_K = 15     # Detailed analysis
    
    # By validation tier (matches rule tier system)
    TIER_1_TOP_K = 8             # Essential validation
    TIER_2_TOP_K = 12            # Standard validation
    TIER_3_TOP_K = 15            # Detailed validation
    TIER_4_TOP_K = 20            # Comprehensive validation
    
    # ============================================
    # RERANKING SETTINGS
    # ============================================
    
    # Enable/disable reranking globally
    ENABLE_RERANKING = True
    
    # Reranking model (cross-encoder for high precision)
    RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"
    
    # When to rerank (by content type)
    RERANK_BY_CONTENT_TYPE = {
        'validation_rule': True,   # [OK] Always rerank validation rules (critical accuracy)
        'interpretation': True,    # [OK] Always rerank interpretations (high-stakes predictions)
        'general': False,          # [FAIL] Skip for general queries (save time)
        'chitchat': False          # [FAIL] Skip for chitchat (not needed)
    }
    
    # Rerank threshold (only rerank if top score < threshold)
    # If the best chunk score is below this, force reranking regardless of content_type
    RERANK_SCORE_THRESHOLD = 0.75
    
    # Retrieve extra chunks before reranking (to give reranker more candidates)
    RERANK_RETRIEVE_MULTIPLIER = 2  # Retrieve 2x chunks, then rerank to top_k
    
    # ============================================
    # CONTEXT EXPANSION SETTINGS
    # ============================================
    
    # Enable/disable context expansion globally
    ENABLE_CONTEXT_EXPANSION = True
    
    # Max adjacent chunks to fetch per direction (±N chunks)
    MAX_ADJACENT_CHUNKS = 2  # ±2 chunks = up to 4 extra chunks per result
    
    # When to expand context (by content type)
    EXPAND_BY_CONTENT_TYPE = {
        'validation_rule': True,   # [OK] Always expand (rules often span multiple chunks)
        'interpretation': False,   # [FAIL] Usually not needed (interpretations are complete)
        'general': False,          # [FAIL] Skip (save time)
        'chitchat': False          # [FAIL] Skip (not relevant)
    }
    
    # Score penalty for adjacent chunks (they're less relevant than original)
    ADJACENT_CHUNK_SCORE_PENALTY = 0.8  # Adjacent chunks get 80% of original score
    
    # ============================================
    # RETRIEVAL STRATEGY SETTINGS
    # ============================================
    
    # Hybrid search weights (semantic, keyword, HyDE)
    HYBRID_WEIGHTS_DEFAULT = (0.5, 0.3, 0.2)
    HYBRID_WEIGHTS_BY_INTENT = {
        "PREDICTION": (0.5, 0.3, 0.2),
        "INTERPRETATION": (0.5, 0.25, 0.25),
        "LEARNING": (0.5, 0.3, 0.2),
        "DEFAULT": (0.5, 0.3, 0.2)
    }
    # Weights tuned per question_mode (overrides intent-based weights when question_mode is set).
    # timing   → higher BM25: exact dasha/period terminology is diagnostic
    # advice   → higher semantic: remedy/guidance chunks match conceptually, not by exact phrase
    # qualities→ higher semantic: planet-quality descriptions are phrased diversely in classical texts
    # summary  → balanced default
    HYBRID_WEIGHTS_BY_QUESTION_MODE = {
        "timing":    (0.40, 0.35, 0.25),
        "advice":    (0.55, 0.20, 0.25),
        "qualities": (0.55, 0.20, 0.25),
        "summary":   (0.50, 0.30, 0.20),
    }
    
    # Retrieval strategies
    USE_HYBRID_SEARCH = True
    USE_RERANKING = True  # Now properly configured
    USE_HYDE = True
    
    # Context expansion
    USE_CONTEXT_EXPANSION = True  # Now properly configured
    MAX_RELATED_CHUNKS = 2
    
    # ============================================
    # SCORING & FILTERING
    # ============================================
    
    SCORE_THRESHOLD = 0.7
    RECIPROCAL_RANK_K = 60  # For RRF fusion
    
    # ============================================
    # HELPER METHODS
    # ============================================
    
    @classmethod
    def get_top_k(
        cls,
        content_type: str = None,
        query_complexity: str = None,
        validation_tier: int = None,
        intent: str = None,
        for_reranking: bool = False
    ) -> int:
        """
        Get appropriate top_k based on context
        
        Priority:
        1. validation_tier (if provided)
        2. content_type (if provided)
        3. query_complexity (if provided)
        4. DEFAULT_TOP_K
        
        Args:
            content_type: 'validation_rule', 'interpretation', 'general', 'chitchat'
            query_complexity: 'simple', 'standard', 'complex'
            validation_tier: 1, 2, 3, or 4
            intent: Intent classification (backward compatibility)
            for_reranking: If True, returns multiplied value for pre-rerank retrieval
            
        Returns:
            Appropriate top_k value
        """
        
        # Priority 1: By validation tier (highest priority)
        if validation_tier is not None:
            tier_map = {
                1: cls.TIER_1_TOP_K,
                2: cls.TIER_2_TOP_K,
                3: cls.TIER_3_TOP_K,
                4: cls.TIER_4_TOP_K
            }
            base_k = tier_map.get(validation_tier, cls.DEFAULT_TOP_K)
        
        # Priority 2: By content type
        elif content_type:
            type_map = {
                'validation_rule': cls.VALIDATION_RULES_TOP_K,
                'interpretation': cls.INTERPRETATIONS_TOP_K,
                'general': cls.GENERAL_KNOWLEDGE_TOP_K,
                'chitchat': cls.CHITCHAT_TOP_K
            }
            base_k = type_map.get(content_type.lower(), cls.DEFAULT_TOP_K)
        
        # Priority 3: By query complexity
        elif query_complexity:
            complexity_map = {
                'simple': cls.SIMPLE_QUERY_TOP_K,
                'standard': cls.STANDARD_QUERY_TOP_K,
                'complex': cls.COMPLEX_QUERY_TOP_K
            }
            base_k = complexity_map.get(query_complexity.lower(), cls.DEFAULT_TOP_K)
        
        # Default
        else:
            base_k = cls.DEFAULT_TOP_K
        
        # If retrieving for reranking, get more candidates
        if for_reranking and cls.ENABLE_RERANKING:
            return base_k * cls.RERANK_RETRIEVE_MULTIPLIER
        
        return base_k
    
    @classmethod
    def should_rerank(
        cls,
        content_type: str = None,
        top_score: float = 1.0,
        query: str = ""
    ) -> bool:
        """
        Decide if reranking should be applied
        
        Args:
            content_type: Type of content being retrieved
            top_score: Score of the top retrieved chunk
            query: User query (for additional heuristics)
            
        Returns:
            True if reranking should be applied
        """
        if not cls.ENABLE_RERANKING:
            return False
        
        # Check content type
        if content_type and cls.RERANK_BY_CONTENT_TYPE.get(content_type, False):
            return True
        
        # Check score threshold (low scores = need reranking)
        if top_score < cls.RERANK_SCORE_THRESHOLD:
            return True
        
        # Additional heuristics based on query
        query_lower = query.lower()
        
        # High-stakes queries should be reranked
        high_stakes_keywords = ['predict', 'when will', 'timing', 'validation', 'check']
        if any(keyword in query_lower for keyword in high_stakes_keywords):
            return True
        
        # Default: no reranking
        return False
    
    @classmethod
    def should_expand(
        cls,
        content_type: str = None,
        chunks: list = None,
        query: str = ""
    ) -> bool:
        """
        Decide if context expansion should be applied
        
        Args:
            content_type: Type of content being retrieved
            chunks: Retrieved chunks (for additional checks)
            query: User query (for additional heuristics)
            
        Returns:
            True if context expansion should be applied
        """
        if not cls.ENABLE_CONTEXT_EXPANSION:
            return False
        
        # Check content type
        if content_type and cls.EXPAND_BY_CONTENT_TYPE.get(content_type, False):
            return True
        
        # Check if any chunks have incomplete sentences
        if chunks:
            for chunk in chunks[:3]:  # Check first 3 chunks
                text = getattr(chunk, 'text', '') or getattr(chunk, 'display_text', '')
                if text and not text.strip().endswith(('.', '।', '?', '!', '॥')):
                    return True  # Incomplete sentence = needs expansion
        
        # Query asks for "complete" or "full" explanation
        query_lower = query.lower()
        complete_keywords = ['complete', 'full', 'detailed', 'comprehensive', 'entire']
        if any(keyword in query_lower for keyword in complete_keywords):
            return True
        
        # Default: no expansion
        return False
    
    @classmethod
    def get_hybrid_weights(cls, intent: str = "DEFAULT", question_mode: str = "") -> tuple:
        """
        Get hybrid search weights for given intent and question_mode.

        question_mode (from SemanticFrame) takes priority over intent when set:
          timing   → higher BM25 (exact period/dasha terms are diagnostic)
          advice   → higher semantic (remedy guidance matches conceptually)
          qualities→ higher semantic (planet-quality descriptions vary in phrasing)
          summary  → balanced default

        Returns:
            (semantic_weight, keyword_weight, hyde_weight)
        """
        if question_mode:
            weights = cls.HYBRID_WEIGHTS_BY_QUESTION_MODE.get(question_mode.lower())
            if weights:
                return weights
        return cls.HYBRID_WEIGHTS_BY_INTENT.get(
            intent.upper(),
            cls.HYBRID_WEIGHTS_DEFAULT
        )


# Backward compatibility - for files that import TOP_K directly
TOP_K = RAGConfig.DEFAULT_TOP_K
VALIDATION_RULES_TOP_K = RAGConfig.VALIDATION_RULES_TOP_K
INTERPRETATIONS_TOP_K = RAGConfig.INTERPRETATIONS_TOP_K
ENABLE_RERANKING = RAGConfig.ENABLE_RERANKING
ENABLE_CONTEXT_EXPANSION = RAGConfig.ENABLE_CONTEXT_EXPANSION


if __name__ == "__main__":
    """Test the configuration"""
    print("=" * 60)
    print("RAG CONFIGURATION TEST")
    print("=" * 60)
    
    print(f"\n[STATS] TOP_K Settings:")
    print(f"  Default: {RAGConfig.DEFAULT_TOP_K}")
    print(f"  Validation rules: {RAGConfig.VALIDATION_RULES_TOP_K}")
    print(f"  Interpretations: {RAGConfig.INTERPRETATIONS_TOP_K}")
    print(f"  General: {RAGConfig.GENERAL_KNOWLEDGE_TOP_K}")
    print(f"  Chitchat: {RAGConfig.CHITCHAT_TOP_K}")
    
    print(f"\n🔄 Reranking Settings:")
    print(f"  Enabled: {RAGConfig.ENABLE_RERANKING}")
    print(f"  Model: {RAGConfig.RERANKER_MODEL}")
    print(f"  Rerank by content type:")
    for ct, enabled in RAGConfig.RERANK_BY_CONTENT_TYPE.items():
        print(f"    {ct}: {enabled}")
    
    print(f"\n📖 Context Expansion Settings:")
    print(f"  Enabled: {RAGConfig.ENABLE_CONTEXT_EXPANSION}")
    print(f"  Max adjacent chunks: ±{RAGConfig.MAX_ADJACENT_CHUNKS}")
    print(f"  Expand by content type:")
    for ct, enabled in RAGConfig.EXPAND_BY_CONTENT_TYPE.items():
        print(f"    {ct}: {enabled}")
    
    print(f"\n🧪 Dynamic Decision Tests:")
    
    # Test reranking decisions
    print(f"\n  Should rerank 'validation_rule'? {RAGConfig.should_rerank('validation_rule')}")
    print(f"  Should rerank 'general' with score 0.9? {RAGConfig.should_rerank('general', 0.9)}")
    print(f"  Should rerank 'general' with score 0.7? {RAGConfig.should_rerank('general', 0.7)}")
    print(f"  Should rerank 'When will I marry?' {RAGConfig.should_rerank(query='When will I get married?')}")
    
    # Test expansion decisions
    print(f"\n  Should expand 'validation_rule'? {RAGConfig.should_expand('validation_rule')}")
    print(f"  Should expand 'interpretation'? {RAGConfig.should_expand('interpretation')}")
    print(f"  Should expand 'Give me complete analysis'? {RAGConfig.should_expand(query='Give me complete analysis')}")
    
    # Test top_k selection
    print(f"\n  Top_k for 'validation_rule': {RAGConfig.get_top_k(content_type='validation_rule')}")
    print(f"  Top_k for 'validation_rule' (pre-rerank): {RAGConfig.get_top_k(content_type='validation_rule', for_reranking=True)}")
    print(f"  Top_k for tier 2: {RAGConfig.get_top_k(validation_tier=2)}")
    
    print("\n" + "=" * 60)
    print("[OK] Configuration loaded successfully")
    print("=" * 60)