# src/routing/semantic_router.py
# src\routing\semantic_router.py

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel
try:
    from src.rag.preprocessing.embedder import Embedder
except ImportError:
    Embedder = None

# Configure logger
logger = logging.getLogger(__name__)

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

    def route(self, query: str, threshold: float = 0.60) -> Optional[RouteResult]:
        """
        Find the best matching route for a query using cosine similarity.
        Returns RouteResult if confidence > threshold, else None.
        """
        if not self.model or getattr(self, 'embedder', None) is None or not self.route_embeddings:
            return None

        # Encode query
        query_embedding = np.array(self.embedder.embed_texts([query])[0])
        
        best_route = None
        best_score = -1.0
        
        # Check against all routes
        for name, route_emb in self.route_embeddings.items():
            scores = []
            for emb in route_emb:
                norm_q = np.linalg.norm(query_embedding)
                norm_e = np.linalg.norm(emb)
                if norm_q == 0 or norm_e == 0:
                    sim = 0.0
                else:
                    sim = np.dot(query_embedding, emb) / (norm_q * norm_e)
                scores.append(sim)
                
            max_score = float(max(scores)) if scores else -1.0
            
            if max_score > best_score:
                best_score = max_score
                best_route = name
        
        # Return result if above threshold
        if best_score >= threshold and best_route:
            return RouteResult(
                name=best_route,
                confidence=best_score,
                metadata=self.routes[best_route]["metadata"]
            )
            
        return None
