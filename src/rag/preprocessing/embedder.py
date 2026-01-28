#!/usr/bin/env python3
"""
Phase 6: Embedding

Generate embeddings using OpenAI text-embedding-3-large model.
"""

import os
import json
import time
import argparse
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
load_dotenv()

# Handle both relative and direct imports
try:
    from .schemas import (
        EnrichedChunk,
        EnrichedDocument,
    )
except ImportError:
    from schemas import (
        EnrichedChunk,
        EnrichedDocument,
    )


class Embedder:
    """
    Generate embeddings using OpenAI text-embedding-3-large.
    """
    
    # OpenAI embedding model
    MODEL = "text-embedding-3-large"
    DIMENSIONS = 3072  # Full dimensionality for best quality
    BATCH_SIZE = 100   # OpenAI batch limit
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize embedder.
        
        Args:
            api_key: OpenAI API key (or from OPENAI_API_KEY env var)
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.client = None
        
        # Initialize cost tracking
        try:
            from src.utils.cost_tracking import CostTrackingWrapper
            self.cost_tracker = CostTrackingWrapper(
                model_name=self.MODEL,
                model_type="embedding"
            )
        except ImportError:
            print("[WARN] Cost tracking not available")
            self.cost_tracker = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                print(f"[OK] OpenAI client initialized")
            except ImportError:
                print("[WARN] openai package not installed. Install with: pip install openai")
        else:
            print("[WARN] OPENAI_API_KEY not set. Embeddings will be skipped.")
    
    def embed_texts(self, texts: List[str], delay: float = 0.5) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            delay: Delay between batches (for rate limiting)
            
        Returns:
            List of embedding vectors
        """
        if not self.client:
            print("[SKIP] No OpenAI client, returning empty embeddings")
            return [[0.0] * self.DIMENSIONS for _ in texts]
        
        all_embeddings = []
        
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i:i + self.BATCH_SIZE]
            
            try:
                response = self.client.embeddings.create(
                    model=self.MODEL,
                    input=batch,
                    dimensions=self.DIMENSIONS,
                )
                
                # Extract embeddings in order
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # Log cost if tracking is available
                if self.cost_tracker and hasattr(response, 'usage'):
                    try:
                        self.cost_tracker.log_from_response(
                            response,
                            operation="embedding",
                            metadata={"batch_num": i//self.BATCH_SIZE + 1, "batch_size": len(batch)}
                        )
                    except Exception as e:
                        print(f"[WARN] Failed to log embedding cost: {e}")
                
                print(f"[OK] Embedded batch {i//self.BATCH_SIZE + 1}/{(len(texts) + self.BATCH_SIZE - 1)//self.BATCH_SIZE}")
                
                # Rate limiting delay
                if i + self.BATCH_SIZE < len(texts):
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"[ERROR] Embedding batch failed: {e}")
                # Return zero vectors for failed batch
                all_embeddings.extend([[0.0] * self.DIMENSIONS for _ in batch])
        
        return all_embeddings
    
    def embed_document(self, enriched_doc: EnrichedDocument) -> EnrichedDocument:
        """
        Add embeddings to all chunks in a document.
        
        Args:
            enriched_doc: Enriched document from Phase 5
            
        Returns:
            Document with embeddings added
        """
        # Extract texts for embedding
        texts = [chunk.text_for_embedding for chunk in enriched_doc.chunks]
        
        print(f"[INFO] Generating embeddings for {len(texts)} chunks...")
        
        # Generate embeddings
        embeddings = self.embed_texts(texts)
        
        # Add embeddings to chunks
        for chunk, embedding in zip(enriched_doc.chunks, embeddings):
            chunk.embedding = embedding
        
        return enriched_doc
    
    def process_file(
        self,
        input_file: str,
        output_file: Optional[str] = None,
    ) -> EnrichedDocument:
        """
        Process an enriched JSON file through Phase 6 embedding.
        
        Args:
            input_file: Path to enriched JSON from Phase 5
            output_file: Optional output path
            
        Returns:
            EnrichedDocument with embeddings
        """
        input_path = Path(input_file)
        
        # Load enriched document
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        enriched_doc = EnrichedDocument(**data)
        
        # Add embeddings
        enriched_doc = self.embed_document(enriched_doc)
        
        # Save output
        if output_file is None:
            output_file = str(input_path.parent / f"{input_path.stem}_embedded.json")
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(enriched_doc.model_dump(), f, ensure_ascii=False, indent=2)
        
        print(f"[OK] Embedded {len(enriched_doc.chunks)} chunks")
        print(f"[OK] Saved to: {output_path}")
        
        return enriched_doc


def test_embedder():
    """Test embedder (requires OPENAI_API_KEY)."""
    print("=" * 70)
    print("EMBEDDER TEST")
    print("=" * 70)
    
    embedder = Embedder()
    
    if embedder.client:
        # Test with sample text
        test_texts = [
            "Gulika in the 5th house affects progeny and education.",
            "Mars in Aries gives courage and leadership qualities.",
        ]
        
        embeddings = embedder.embed_texts(test_texts)
        
        print(f"\n[OK] Generated {len(embeddings)} embeddings")
        print(f"[OK] Embedding dimension: {len(embeddings[0])}")
        print(f"[OK] First few values: {embeddings[0][:5]}")
    else:
        print("[SKIP] No API key, skipping actual embedding test")


if __name__ == "__main__":
    def main():
        """CLI entry point."""
        parser = argparse.ArgumentParser(
            description="Phase 6: Embedding - Generate embeddings using OpenAI text-embedding-3-large."
        )
        parser.add_argument(
            "input_file", 
            nargs="?", 
            help="Path to enriched JSON file from Phase 5"
        )
        parser.add_argument(
            "--output", 
            "-o", 
            help="Optional output path"
        )
        parser.add_argument(
            "--test", 
            action="store_true", 
            help="Run simple test with dummy data"
        )
        
        args = parser.parse_args()
        
        if args.test:
            test_embedder()
            return

        if not args.input_file:
            parser.print_help()
            print("\n[ERROR] input_file argument is required unless --test is specified.")
            return

        embedder = Embedder()
        embedder.process_file(args.input_file, args.output)

    main()
