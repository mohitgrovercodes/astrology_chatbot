
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel
try:
    from sentence_transformers import SentenceTransformer, util
except ImportError:
    SentenceTransformer = None
    util = None

# Configure logger
logger = logging.getLogger(__name__)

class RouteResult(BaseModel):
    name: str
    confidence: float
    metadata: Dict[str, Any] = {}

class SemanticRouter:
    _instance = None
    
    def __new__(cls, model_name: str = 'all-MiniLM-L6-v2'):
        if cls._instance is None:
            cls._instance = super(SemanticRouter, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize Semantic Router with a lightweight embedding model.
        Uses Singleton pattern to avoid reloading model.
        """
        if self._initialized:
            return
            
        self.model_name = model_name
        self.routes: Dict[str, Any] = {}
        self.route_embeddings: Dict[str, Any] = {}
        
        # Load model with lazy loading check
        if SentenceTransformer:
            try:
                logger.info(f"Loading semantic routing model: {model_name}")
                self.model = SentenceTransformer(model_name)
                self._initialized = True
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                self.model = None
        else:
            logger.warning("sentence-transformers not installed. Semantic Routing disabled.")
            self.model = None

    def add_route(self, name: str, examples: List[str], metadata: Dict[str, Any] = None):
        """
        Add a semantic route with example utterances.
        Examples are immediately embedded and cached.
        """
        if not self.model:
            return

        logger.info(f"Adding semantic route: {name} ({len(examples)} examples)")
        embeddings = self.model.encode(examples, convert_to_tensor=True)
        
        self.routes[name] = {
            "examples": examples,
            "metadata": metadata or {}
        }
        self.route_embeddings[name] = embeddings

    def route(self, query: str, threshold: float = 0.60) -> Optional[RouteResult]:
        """
        Find the best matching route for a query using cosine similarity.
        Returns RouteResult if confidence > threshold, else None.
        """
        if not self.model or not self.route_embeddings:
            return None

        # Encode query
        query_embedding = self.model.encode(query, convert_to_tensor=True)
        
        best_route = None
        best_score = -1.0
        
        # Check against all routes
        for name, route_emb in self.route_embeddings.items():
            # Calculate cosine similarity
            # util.cos_sim returns a tensor [[score]]
            scores = util.cos_sim(query_embedding, route_emb)[0]
            max_score = float(scores.max())
            
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
