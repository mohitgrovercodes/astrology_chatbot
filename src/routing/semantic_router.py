# src/routing/semantic_router.py

import hashlib
import json
import numpy as np
import logging
import pickle
from pathlib import Path
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

# ── Disk-cache directory (project-relative) ────────────────────────────────
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "route_cache"


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
    Semantic router backed by OpenAI embeddings with disk-caching.

    Startup optimisations:
    - Route embeddings are persisted to disk keyed by a hash of the examples.
      On the SECOND and every subsequent server start the cache is loaded in
      milliseconds — NO OpenAI API call is made.
    - add_routes_batch() embeds ALL routes in a SINGLE API call, reducing the
      N-routes × 1-API-call pattern to exactly 1 call on a cold start.
    """

    _instance = None

    def __new__(cls, model_name: str = 'text-embedding-3-large'):
        if cls._instance is None:
            cls._instance = super(SemanticRouter, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = 'text-embedding-3-large'):
        if self._initialized:
            return

        self.model_name = model_name
        self.routes: Dict[str, Any] = {}
        self.route_embeddings: Dict[str, Any] = {}

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

        if Embedder:
            try:
                logger.info(f"Loading semantic routing model (OpenAI): {model_name}")
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
    # CACHE HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def _cache_key(self, name: str, examples: List[str]) -> str:
        """Stable hash for (route_name, examples, model) triplet."""
        payload = json.dumps({"name": name, "examples": sorted(examples), "model": self.model_name},
                             sort_keys=True)
        return hashlib.md5(payload.encode()).hexdigest()

    def _cache_path(self, cache_key: str) -> Path:
        return _CACHE_DIR / f"{cache_key}.pkl"

    def _load_from_cache(self, cache_key: str) -> Optional[np.ndarray]:
        p = self._cache_path(cache_key)
        if p.exists():
            try:
                with open(p, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"[ROUTER CACHE] Failed to load cache {p}: {e}")
        return None

    def _save_to_cache(self, cache_key: str, embeddings: np.ndarray):
        p = self._cache_path(cache_key)
        try:
            with open(p, "wb") as f:
                pickle.dump(embeddings, f)
        except Exception as e:
            logger.warning(f"[ROUTER CACHE] Failed to save cache {p}: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # ROUTE REGISTRATION
    # ──────────────────────────────────────────────────────────────────────────

    def add_route(self, name: str, examples: List[str], metadata: Dict[str, Any] = None):
        """
        Add a single semantic route. Embeddings are disk-cached so the OpenAI
        API is only called once per unique (name, examples) pair.
        """
        if not self.model or getattr(self, 'embedder', None) is None:
            return

        cache_key = self._cache_key(name, examples)
        embeddings_arr = self._load_from_cache(cache_key)

        if embeddings_arr is not None:
            logger.info(f"[ROUTER CACHE] HIT — loaded '{name}' from disk ({len(examples)} examples)")
        else:
            logger.info(f"[ROUTER CACHE] MISS — embedding '{name}' via API ({len(examples)} examples)")
            raw = self.embedder.embed_texts(examples)
            embeddings_arr = np.array(raw)
            self._save_to_cache(cache_key, embeddings_arr)

        self.routes[name] = {"examples": examples, "metadata": metadata or {}}
        self.route_embeddings[name] = embeddings_arr

    def add_routes_batch(self, routes: List[Dict[str, Any]]):
        """
        Register multiple routes in a SINGLE batched API call (fast path).

        routes: list of dicts with keys 'name', 'examples', 'metadata' (optional).

        Algorithm:
        1. Check disk cache for each route.
        2. Collect ALL uncached examples into one flat list.
        3. Make a *single* embed_texts() call for all missing examples.
        4. Distribute embeddings back and cache each route.
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
            cache_key = self._cache_key(name, examples)
            cached = self._load_from_cache(cache_key)

            if cached is not None:
                logger.info(f"[ROUTER CACHE] HIT — loaded '{name}' from disk ({len(examples)} examples)")
                self.routes[name] = {"examples": examples, "metadata": metadata}
                self.route_embeddings[name] = cached
            else:
                start = len(pending_texts)
                pending_texts.extend(examples)
                end = len(pending_texts)
                pending_offsets.append((start, end))
                pending_routes.append({"name": name, "examples": examples, "metadata": metadata,
                                       "cache_key": cache_key})

        if pending_texts:
            logger.info(f"[ROUTER CACHE] MISS — batching {len(pending_texts)} examples "
                        f"for {len(pending_routes)} routes in ONE API call")
            print(f"[SEMANTIC_ROUTER] Embedding {len(pending_texts)} examples "
                  f"for {len(pending_routes)} routes in one batch...")
            all_embeddings = self.embedder.embed_texts(pending_texts)

            for i, prt in enumerate(pending_routes):
                start, end = pending_offsets[i]
                arr = np.array(all_embeddings[start:end])
                self.routes[prt["name"]] = {"examples": prt["examples"], "metadata": prt["metadata"]}
                self.route_embeddings[prt["name"]] = arr
                self._save_to_cache(prt["cache_key"], arr)
                logger.info(f"[ROUTER CACHE] Cached '{prt['name']}' to disk")

        print(f"[SEMANTIC_ROUTER] {len(routes)} routes ready "
              f"({len(routes) - len(pending_routes)} from cache, "
              f"{len(pending_routes)} newly embedded)")

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