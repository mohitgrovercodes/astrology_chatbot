# src/routing/semantic_router.py

import json
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
class RouteMatch:
    name: str
    confidence: float


class RouteResult(BaseModel):
    name: str
    confidence: float
    metadata: Dict[str, Any] = {}


class SemanticRouter:
    """
    Semantic router backed by Vertex AI embeddings.

    Startup optimisations:
    - add_routes_batch() embeds ALL routes in a SINGLE API call, reducing the
      N-routes × 1-API-call pattern to exactly 1 call on a cold start.
    """

    _instance = None

    def __new__(cls, model_name: str = 'gemini-embedding-001'):
        if cls._instance is None:
            cls._instance = super(SemanticRouter, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = 'gemini-embedding-001'):
        if self._initialized:
            return

        self.model_name = model_name
        self.routes: Dict[str, Any] = {}
        self.route_embeddings: Dict[str, Any] = {}

        if Embedder:
            try:
                logger.info(f"Loading semantic routing model (Vertex AI): {model_name}")
                self.embedder = Embedder(model=model_name)
                self.model = True
                self._initialized = True
            except Exception as e:
                logger.error(f"Error initializing Embedder in SemanticRouter: {e}")
                self.model = None
                self.embedder = None
        else:
            logger.warning("Embedder unavailable. Semantic Routing disabled.")
            self.model = None
            self.embedder = None

    # ──────────────────────────────────────────────────────────────────────────
    # ROUTE REGISTRATION
    # ──────────────────────────────────────────────────────────────────────────

    def add_route(self, name: str, examples: List[str], metadata: Dict[str, Any] = None):
        """
        Add a single semantic route.
        """
        if not self.model or getattr(self, 'embedder', None) is None:
            return

        logger.info(f"[ROUTER] embedding '{name}' via API ({len(examples)} examples)")
        raw = self.embedder.embed_texts(examples)
        embeddings_arr = np.array(raw)

        self.routes[name] = {"examples": examples, "metadata": metadata or {}}
        self.route_embeddings[name] = embeddings_arr

    def add_routes_batch(self, routes: List[Dict[str, Any]]):
        """
        Register multiple routes in a SINGLE batched API call (fast path).

        routes: list of dicts with keys 'name', 'examples', 'metadata' (optional).
        """
        if not self.model or getattr(self, 'embedder', None) is None:
            return

        pending_routes: List[Dict] = []   # routes that need API embedding
        pending_texts: List[str] = []     # flat list of all uncached examples
        pending_offsets: List[Tuple[int, int]] = []  # (start, end) in pending_texts for each pending route

        for route in routes:
            name = route["name"]
            examples = route["examples"]
            metadata = route.get("metadata", {})
            
            start = len(pending_texts)
            pending_texts.extend(examples)
            end = len(pending_texts)
            pending_offsets.append((start, end))
            pending_routes.append({"name": name, "examples": examples, "metadata": metadata})

        if pending_texts:
            logger.info(f"[ROUTER] batching {len(pending_texts)} examples "
                        f"for {len(pending_routes)} routes in ONE API call")
            print(f"[SEMANTIC_ROUTER] Embedding {len(pending_texts)} examples "
                  f"for {len(pending_routes)} routes in one batch...")
            
            all_embeddings = self.embedder.embed_texts(pending_texts)

            for i, prt in enumerate(pending_routes):
                start, end = pending_offsets[i]
                arr = np.array(all_embeddings[start:end])
                self.routes[prt["name"]] = {"examples": prt["examples"], "metadata": prt["metadata"]}
                self.route_embeddings[prt["name"]] = arr
                logger.info(f"[ROUTER] Loaded '{prt['name']}' in memory")

        print(f"[SEMANTIC_ROUTER] {len(routes)} routes ready "
              f"({len(pending_routes)} newly embedded)")

    # ──────────────────────────────────────────────────────────────────────────
    # ROUTING
    # ──────────────────────────────────────────────────────────────────────────

    def route(self, query: str, threshold: float = 0.7) -> Optional[RouteMatch]:
        """Route a query to the most similar route using semantic similarity."""
        if not self.model:
            print("[SEMANTIC_ROUTER] Model not loaded - skipping routing")
            return None

        try:
            embeddings = self.embedder.embed_texts([query])
            if not embeddings or len(embeddings) == 0:
                print("[SEMANTIC_ROUTER] WARNING: Empty embedding response")
                return None
            query_embedding = np.array(embeddings[0])
        except Exception as e:
            print(f"[SEMANTIC_ROUTER] ERROR: Failed to embed query: {e}")
            return None

        max_score = None
        max_idx = None
        best_route_name = None

        try:
            route_names = list(self.routes.keys())

            if not route_names:
                print("[SEMANTIC_ROUTER] WARNING: No routes registered")
                return None

            embedding_matrix = np.array([
                np.mean(self.route_embeddings[name], axis=0)
                for name in route_names
            ])

            similarities = cosine_similarity([query_embedding], embedding_matrix)[0]
            max_idx = np.argmax(similarities)
            max_score = float(similarities[max_idx])
            best_route_name = route_names[max_idx]

            print(f"[SEMANTIC_ROUTER] Top match: {best_route_name} (confidence: {max_score:.3f})")

            if max_score >= threshold:
                return RouteMatch(name=best_route_name, confidence=max_score)

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