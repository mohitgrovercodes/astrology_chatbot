#!/usr/bin/env python3
"""
Phase 6: Embedding

Production-ready embedding generation using OpenAI models.
Includes exponential backoff retries, centralized logging, and cost tracking.
"""

import os
import json
import time
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Project imports
try:
    from src.utils.config import get_config
    from src.utils.logger import get_logger
    from src.utils.cost_tracking import CostTrackingWrapper
    from .schemas import EnrichedChunk, EnrichedDocument
    logger = get_logger(__name__)
    CONFIG_AVAILABLE = True
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    CONFIG_AVAILABLE = False
    # Local fallback for schemas if not in package mode
    try:
        from schemas import EnrichedChunk, EnrichedDocument
    except ImportError:
        # Define minimal classes for standalone operation if schemas are missing
        from pydantic import BaseModel
        class EnrichedChunk(BaseModel):
            chunk_id: str
            text_for_embedding: str
            embedding: Optional[List[float]] = None
        class EnrichedDocument(BaseModel):
            chunks: List[EnrichedChunk]

class Embedder:
    """
    Production-grade Embedder with robust error handling and cost tracking.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize embedder.
        
        Args:
            api_key: OpenAI API key
            model: Model name (defaults to config)
        """
        if CONFIG_AVAILABLE:
            config = get_config()
            self.model = model or config.embeddings.model
            self.dimensions = config.embeddings.dimensions
            self.api_key = api_key or config.get_api_key('openai')
        else:
            self.model = model or "text-embedding-3-large"
            self.dimensions = 1536  # Use 1536 to match collection (not default 3072)
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

        self.client = None
        self.batch_size = 100
        
        # Initialize client
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info(f"OK: OpenAI Embedder initialized: {self.model}")
            except ImportError:
                logger.error("ERROR: openai package not installed. Run: pip install openai")
        else:
            logger.warning("WARN: OPENAI_API_KEY not set. Embedding will yield zero-vectors.")

        # Initialize cost tracking
        try:
            from src.utils.cost_tracking import CostTrackingWrapper
            self.cost_tracker = CostTrackingWrapper(
                model_name=self.model,
                model_type="embedding"
            )
        except ImportError:
            self.cost_tracker = None

    def embed_texts(self, texts: List[str], max_retries: int = 5) -> List[List[float]]:
        """
        Generate embeddings with exponential backoff retries.
        """
        if not self.client:
            logger.error("No OpenAI client available. Returning zero-vectors.")
            return [[0.0] * self.dimensions for _ in texts]
        
        all_embeddings = []
        current_batch_size = self.batch_size
        
        for i in range(0, len(texts), current_batch_size):
            batch = texts[i:i + current_batch_size]
            attempt = 0
            success = False
            
            while attempt < max_retries and not success:
                try:
                    response = self.client.embeddings.create(
                        model=self.model,
                        input=batch,
                        dimensions=self.dimensions if "3-" in self.model else None,
                    )
                    
                    batch_embeddings = [item.embedding for item in response.data]
                    all_embeddings.extend(batch_embeddings)
                    
                    # Track cost
                    if self.cost_tracker:
                        self.cost_tracker.log_from_response(response)
                    
                    success = True
                    logger.info(f"OK: Embedded batch {i//current_batch_size + 1}/{(len(texts) + current_batch_size - 1)//current_batch_size}")
                    
                except Exception as e:
                    attempt += 1
                    error_msg = str(e).lower()
                    
                    if any(x in error_msg for x in ["429", "rate limit", "too many requests"]):
                        wait_time = (2 ** attempt + 1)
                        logger.warning(f"WAIT: Rate limit hit. Retrying in {wait_time}s... (Attempt {attempt}/{max_retries})")
                        time.sleep(wait_time)
                        
                        # Dynamic batch sizing
                        if current_batch_size > 10:
                            current_batch_size = current_batch_size // 2
                            logger.info(f"INFO: Reducing batch size to {current_batch_size}")
                    else:
                        logger.error(f"ERROR: Embedding failed: {e}")
                        if attempt >= max_retries:
                            logger.critical("CRITICAL: Max retries reached. Filling batch with zero-vectors.")
                            all_embeddings.extend([[0.0] * self.dimensions for _ in batch])
                            success = True 
                        else:
                            time.sleep(1)

        return all_embeddings

    def embed_document(self, enriched_doc: EnrichedDocument) -> EnrichedDocument:
        """Process an entire EnrichedDocument."""
        texts = [chunk.text_for_embedding for chunk in enriched_doc.chunks]
        if not texts:
            logger.warning("No chunks found in document.")
            return enriched_doc
            
        logger.info(f"START: Generating embeddings for {len(texts)} chunks...")
        embeddings = self.embed_texts(texts)
        
        for chunk, embedding in zip(enriched_doc.chunks, embeddings):
            chunk.embedding = embedding
            
        return enriched_doc

    def process_file(self, input_file: str, output_file: Optional[str] = None):
        """Standalone file processing."""
        input_path = Path(input_file)
        if not input_path.exists():
            logger.error(f"File not found: {input_file}")
            return

        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Load schema
        try:
            enriched_doc = EnrichedDocument(**data)
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            return

        enriched_doc = self.embed_document(enriched_doc)
        
        output_path = Path(output_file) if output_file else input_path.parent / f"{input_path.stem}_embedded.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            if hasattr(enriched_doc, "model_dump"):
                json.dump(enriched_doc.model_dump(), f, ensure_ascii=False, indent=2)
            else:
                json.dump(enriched_doc.dict(), f, ensure_ascii=False, indent=2)
                
        logger.info(f"SUCCESS: Successfully processed and saved to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 6: Embedder (Production Version)")
    parser.add_argument("input", help="Path to input JSON file", nargs="?")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--test", action="store_true", help="Run a quick test")
    
    args = parser.parse_args()
    
    embedder = Embedder()
    
    if args.test:
        print("Running Embedder Test...")
        test_text = ["Gulika in the 5th house is auspicious.", "Mars in Aries gives courage."]
        vecs = embedder.embed_texts(test_text)
        print(f"DONE: Generated {len(vecs)} vectors of size {len(vecs[0])}")
    elif args.input:
        embedder.process_file(args.input, args.output)
    else:
        parser.print_help()
