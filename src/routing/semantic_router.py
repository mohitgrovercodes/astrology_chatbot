# src/routing/semantic_router.py
# src\routing\semantic_router.py

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel
from dataclasses import dataclass 
from sklearn.metrics.pairwise import cosine_similarity

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
        """
        if not self.model:
            print("[SEMANTIC_ROUTER] Model not loaded - skipping routing")
            return None
        
        # Defensive: Handle empty embedding response
        try:
            embeddings = self.embedder.embed_texts([query])
            
            if not embeddings or len(embeddings) == 0:
                print(f"[SEMANTIC_ROUTER] WARNING: Empty embedding response")
                return None
            
            query_embedding = np.array(embeddings[0])
            
        except Exception as e:
            print(f"[SEMANTIC_ROUTER] ERROR: Failed to embed query: {e}")
            return None
        
        # Find most similar route
        max_score = None
        max_idx = None
        best_route_name = None
        
        try:
            # Build embedding matrix from route_embeddings dict
            # self.route_embeddings is {route_name: np.array(embeddings), ...}
            route_names = list(self.routes.keys())
            
            if not route_names:
                print("[SEMANTIC_ROUTER] WARNING: No routes registered")
                return None
            
            # Stack all route embeddings into a 2D array
            # Each row is the mean embedding of all examples for that route
            embedding_matrix = np.array([
                np.mean(self.route_embeddings[name], axis=0) 
                for name in route_names
            ])
            
            # Compute similarities: [1 x route_count]
            similarities = cosine_similarity([query_embedding], embedding_matrix)[0]
            max_idx = np.argmax(similarities)
            max_score = float(similarities[max_idx])  # Convert to Python float immediately
            best_route_name = route_names[max_idx]
            
            print(f"[SEMANTIC_ROUTER] Top match: {best_route_name} (confidence: {max_score:.3f})")
            
            if max_score >= threshold:
                return RouteMatch(
                    name=best_route_name,
                    confidence=max_score
                )
            
            return None
            
        except TypeError as e:
            print(f"[SEMANTIC_ROUTER] ERROR: Type conversion failed: {e}")
            if max_score is not None:
                print(f"[SEMANTIC_ROUTER] max_score type: {type(max_score)}, value: {max_score}")
            return None
        except Exception as e:
            print(f"[SEMANTIC_ROUTER] ERROR: Similarity calculation failed: {e}")
            import traceback
            traceback.print_exc()
            return None