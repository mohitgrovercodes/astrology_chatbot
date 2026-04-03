# src/rag/preprocessing/embedder.py
# src\rag\preprocessing\embedder.py
#!/usr/bin/env python3
"""
Phase 6: Embedding

Production-ready embedding generation using Google Vertex AI models.
Includes exponential backoff retries and centralized logging.
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
    Production-grade Embedder using Google Vertex AI with robust error handling.
    """

    def __init__(self, model: Optional[str] = None, project: Optional[str] = None, location: Optional[str] = None):
        """
        Initialize embedder.

        Args:
            model: Model name (defaults to config or text-embedding-004)
            project: Google Cloud project ID
            location: Google Cloud location
        """
        if CONFIG_AVAILABLE:
            config = get_config()
            self.model = model or config.embeddings.model
            self.dimensions = config.embeddings.dimensions
        else:
            self.model = model or "gemini-embedding-001"
            self.dimensions = 1536

        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.client = None
        self.batch_size = 100

        # Initialize client
        if self.project:
            try:
                from langchain_google_vertexai import VertexAIEmbeddings
                self.client = VertexAIEmbeddings(
                    model_name=self.model,
                    project=self.project,
                    location=self.location,
                    output_dimensionality=self.dimensions,
                )
                logger.info(f"OK: Vertex AI Embedder initialized: {self.model} (project={self.project})")
            except ImportError:
                logger.error("ERROR: langchain-google-vertexai not installed. Run: pip install langchain-google-vertexai google-cloud-aiplatform")
        else:
            logger.warning("WARN: GOOGLE_CLOUD_PROJECT not set. Embedding will yield zero-vectors.")

    def embed_texts(self, texts: List[str], max_retries: int = 5) -> List[List[float]]:
        """
        Generate embeddings with exponential backoff retries.
        """
        if not self.client:
            logger.error("No Vertex AI client available. Returning zero-vectors.")
            return [[0.0] * self.dimensions for _ in texts]

        all_embeddings = []
        current_batch_size = self.batch_size

        for i in range(0, len(texts), current_batch_size):
            batch = texts[i:i + current_batch_size]
            attempt = 0
            success = False

            while attempt < max_retries and not success:
                try:
                    batch_embeddings = self.client.embed_documents(batch)
                    all_embeddings.extend(batch_embeddings)
                    success = True
                    logger.info(f"OK: Embedded batch {i//current_batch_size + 1}/{(len(texts) + current_batch_size - 1)//current_batch_size}")

                except Exception as e:
                    attempt += 1
                    error_msg = str(e).lower()

                    if any(x in error_msg for x in ["429", "rate limit", "too many requests", "resource exhausted", "quota"]):
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
    parser = argparse.ArgumentParser(description="Phase 6: Embedder (Vertex AI)")
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
