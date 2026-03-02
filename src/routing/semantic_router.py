# src/routing/semantic_router.py
# src\routing\semantic_router.py

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel
from dataclasses import dataclass 

try:
    from src.rag.preprocessing.embedder import Embedder
except ImportError:
    Embedder = None

# Configure logger
logger = logging.getLogger(__name__)

@dataclass
class Route:
    name: str
    utterances: List[str]

@dataclass
class RouteMatch:  # ← THIS IS MISSING
    name: str
    confidence: float

class RouteResult(BaseModel):
    name: str
    confidence: float
    metadata: Dict[str, Any] = {}

class SemanticRouter:
    _instance = None
    
    def __new__(cls, model_name: str = 'text-embedding-3-large'):
        if cls._instance is None:
            cls._instance = super(SemanticRouter, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = 'text-embedding-3-large'):
        """
        Initialize Semantic Router with OpenAI Embedder.
        Uses Singleton pattern to avoid reloading model.
        """
        if self._initialized:
            return
            
        self.model_name = model_name
        self.routes: Dict[str, Any] = {}
        self.route_embeddings: Dict[str, Any] = {}
        
        # Load model
        if Embedder:
            try:
                logger.info(f"Loading semantic routing model (OpenAI): {model_name}")
                self.embedder = Embedder(model=model_name)
                self.model = True # Setup flag
                self._initialized = True
            except Exception as e:
                logger.error(f"Error initializing Embedder in SemanticRouter: {e}")
                self.model = None
                self.embedder = None
        else:
            logger.warning("Embedder unavailable. Semantic Routing disabled.")
            self.model = None
            self.embedder = None

    def add_route(self, name: str, examples: List[str], metadata: Dict[str, Any] = None):
        """
        Add a semantic route with example utterances.
        Examples are immediately embedded and cached.
        """
        if not self.model or getattr(self, 'embedder', None) is None:
            return

        logger.info(f"Adding semantic route: {name} ({len(examples)} examples)")
        embeddings = self.embedder.embed_texts(examples)
        
        self.routes[name] = {
            "examples": examples,
            "metadata": metadata or {}
        }
        self.route_embeddings[name] = np.array(embeddings)

    def route(self, query: str, threshold: float = 0.7) -> Optional[RouteMatch]:
        """
        Route a query to the most similar route using semantic similarity.
        Returns None if routing fails (allows graceful fallback).
        """
        if not self.model:
            print("[SEMANTIC_ROUTER] Model not loaded - skipping routing")
            return None
        
        # ════════════════════════════════════════════════════════════════
        # DEFENSIVE: Handle empty embedding response (rate limit/error)
        # ════════════════════════════════════════════════════════════════
        try:
            embeddings = self.embedder.embed_texts([query])
            
            # Check if embedder returned empty list
            if not embeddings or len(embeddings) == 0:
                print(f"[SEMANTIC_ROUTER] WARNING: Empty embedding response for query: '{query[:50]}...'")
                print(f"[SEMANTIC_ROUTER] Falling back to non-semantic classification")
                return None  # Graceful fallback
            
            query_embedding = np.array(embeddings[0])
            
        except Exception as e:
            print(f"[SEMANTIC_ROUTER] ERROR: Failed to embed query: {e}")
            import traceback
            traceback.print_exc()
            return None  # Graceful fallback
        
        # Find most similar route
        try:
            similarities = cosine_similarity([query_embedding], self.route_embeddings)[0]
            max_idx = np.argmax(similarities)
            max_score = similarities[max_idx]
            
            if max_score >= threshold:
                return RouteMatch(
                    name=self.routes[max_idx].name,
                    confidence=float(max_score)
                )
            
            return None
            
        except Exception as e:
            print(f"[SEMANTIC_ROUTER] ERROR: Similarity calculation failed: {e}")
            return None
