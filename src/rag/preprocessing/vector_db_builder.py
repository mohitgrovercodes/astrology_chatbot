# src/rag/preprocessing/vector_db_builder.py
# src\rag\preprocessing\vector_db_builder.py
#!/usr/bin/env python3
"""
Phase 7: Vector Database Builder

Ingest embedded chunks into ChromaDB for semantic search.
"""

import os
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List

# Disable ChromaDB telemetry before import to suppress capture() errors
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["CHROMA_TELEMETRY"] = "false"
import chromadb
from chromadb.config import Settings

# Handle both relative and direct imports
try:
    from .schemas import EnrichedDocument, EnrichedChunk
except ImportError:
    from schemas import EnrichedDocument, EnrichedChunk


class VectorDBBuilder:
    """
    Build and manage ChromaDB vector database for RAG retrieval.
    """
    
    def __init__(
        self,
        db_path: str = "data/vectordb",
        collection_name: Optional[str] = None,
    ):
        """
        Initialize ChromaDB client.
        
        Args:
            db_path: Path to ChromaDB persistent storage
            collection_name: Name of the collection (default: auto-generated)
        """
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )
        
        self.collection_name = collection_name
        self.collection = None
        
        print(f"[OK] ChromaDB initialized at: {self.db_path}")
    
    def create_collection(
        self,
        collection_name: str,
        reset: bool = False,
    ) -> chromadb.Collection:
        """
        Create or get ChromaDB collection.
        
        Args:
            collection_name: Name of the collection
            reset: If True, delete existing collection and create new one
            
        Returns:
            ChromaDB collection object
        """
        self.collection_name = collection_name
        
        # Reset if requested
        if reset:
            try:
                self.client.delete_collection(name=collection_name)
                print(f"[OK] Deleted existing collection: {collection_name}")
            except Exception:
                pass  # Collection doesn't exist
        
        # Create or get collection with cosine similarity
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},  # Cosine similarity for embeddings
        )
        
        print(f"[OK] Collection ready: {collection_name}")
        print(f"[INFO] Current count: {self.collection.count()} chunks")
        
        return self.collection
    
    def _prepare_metadata(self, chunk: EnrichedChunk) -> Dict[str, Any]:
        """
        Convert EnrichedChunk metadata to ChromaDB-compatible format.
        
        ChromaDB metadata constraints:
        - Values must be: str, int, float, or bool
        - No nested objects or lists of objects
        
        Args:
            chunk: EnrichedChunk object
            
        Returns:
            Flattened metadata dictionary
        """
        metadata = {
            "chunk_id": chunk.chunk_id,
            "unit_id": chunk.unit_id,
            "source_book": chunk.metadata.source_book,
            "tradition": chunk.metadata.tradition,
            "token_count": chunk.token_count,
            "has_verse": chunk.verse_sanskrit is not None,
        }
        
        # Add optional fields
        if chunk.metadata.chapter:
            metadata["chapter"] = chunk.metadata.chapter
        if chunk.metadata.section:
            metadata["section"] = chunk.metadata.section
        if chunk.metadata.verse_number:
            metadata["verse_number"] = chunk.metadata.verse_number
        
        # Flatten entity lists as comma-separated strings
        entities = chunk.metadata.entities
        if entities.planets:
            metadata["planets"] = ",".join(entities.planets)
        if entities.houses:
            metadata["houses"] = ",".join(entities.houses)
        if entities.signs:
            metadata["signs"] = ",".join(entities.signs)
        if entities.nakshatras:
            metadata["nakshatras"] = ",".join(entities.nakshatras)
        if entities.yogas:
            metadata["yogas"] = ",".join(entities.yogas)
        if entities.concepts:
            metadata["concepts"] = ",".join(entities.concepts)
        
        # Store source pages as JSON string
        if chunk.source_pages:
            metadata["source_pages"] = json.dumps(chunk.source_pages)
        
        return metadata
    
    def insert_chunks(
        self,
        enriched_doc: EnrichedDocument,
        batch_size: int = 100,
    ) -> int:
        """
        Insert chunks from EnrichedDocument into ChromaDB.
        
        Args:
            enriched_doc: EnrichedDocument with embeddings
            batch_size: Number of chunks to insert per batch
            
        Returns:
            Number of chunks successfully inserted
        """
        if not self.collection:
            raise ValueError("Collection not initialized. Call create_collection() first.")
        
        # Filter chunks with valid embeddings
        valid_chunks = [
            c for c in enriched_doc.chunks
            if c.embedding and len(c.embedding) > 0 and any(e != 0 for e in c.embedding)
        ]
        
        if not valid_chunks:
            print("[WARN] No valid embeddings found in document")
            return 0
        
        print(f"[INFO] Inserting {len(valid_chunks)} chunks into ChromaDB...")
        
        inserted_count = 0
        
        # Process in batches
        for i in range(0, len(valid_chunks), batch_size):
            batch = valid_chunks[i:i + batch_size]
            
            # Prepare batch data
            ids = [chunk.chunk_id for chunk in batch]
            embeddings = [chunk.embedding for chunk in batch]
            documents = [chunk.text_for_embedding for chunk in batch]
            metadatas = [self._prepare_metadata(chunk) for chunk in batch]
            
            try:
                # Upsert (insert or update)
                self.collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )
                
                inserted_count += len(batch)
                print(f"  [OK] Batch {i//batch_size + 1}/{(len(valid_chunks) + batch_size - 1)//batch_size} inserted")
                
            except Exception as e:
                print(f"  [ERROR] Batch {i//batch_size + 1} failed: {e}")
        
        print(f"[OK] Inserted {inserted_count} chunks")
        print(f"[INFO] Total collection size: {self.collection.count()}")
        
        return inserted_count
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current collection.
        
        Returns:
            Dictionary with collection statistics
        """
        if not self.collection:
            return {"error": "No collection initialized"}
        
        count = self.collection.count()
        
        # Sample metadata to get unique values
        stats = {
            "collection_name": self.collection_name,
            "total_chunks": count,
            "db_path": str(self.db_path),
        }
        
        if count > 0:
            # Get a sample to analyze metadata
            sample = self.collection.get(limit=min(100, count), include=["metadatas"])
            
            if sample and sample.get("metadatas"):
                metadatas = sample["metadatas"]
                
                # Count unique values
                books = set(m.get("source_book") for m in metadatas if m.get("source_book"))
                chapters = set(m.get("chapter") for m in metadatas if m.get("chapter"))
                traditions = set(m.get("tradition") for m in metadatas if m.get("tradition"))
                
                stats["unique_books"] = len(books)
                stats["unique_chapters"] = len(chapters)
                stats["traditions"] = list(traditions)
                stats["has_verses"] = sum(1 for m in metadatas if m.get("has_verse"))
        
        return stats
    
    def process_file(
        self,
        input_file: str,
        collection_name: Optional[str] = None,
        reset: bool = False,
    ) -> Dict[str, Any]:
        """
        Process an embedded JSON file and insert into ChromaDB.
        
        Args:
            input_file: Path to embedded JSON from Phase 6
            collection_name: Collection name (default: derived from source_book)
            reset: Clear existing collection before inserting
            
        Returns:
            Statistics dictionary
        """
        input_path = Path(input_file)
        
        # Load enriched document
        print(f"[INFO] Loading: {input_path.name}")
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        enriched_doc = EnrichedDocument(**data)
        
        # Determine collection name
        if not collection_name:
            # Try to extract from first chunk's metadata
            if enriched_doc.chunks:
                source_book = enriched_doc.chunks[0].metadata.source_book
                # Sanitize collection name (ChromaDB requirements)
                collection_name = source_book.lower().replace(" ", "_").replace("-", "_")
            else:
                collection_name = "vedic_astrology_books_knowledge"
        
        # Create collection
        self.create_collection(collection_name, reset=reset)
        
        # Insert chunks
        inserted = self.insert_chunks(enriched_doc)
        
        # Get stats
        stats = self.get_collection_stats()
        stats["inserted_this_run"] = inserted
        
        return stats


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Phase 7: Vector Database Builder - Ingest chunks into ChromaDB."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to embedded JSON file from Phase 6"
    )
    parser.add_argument(
        "--db-path",
        default="data/vectordb",
        help="ChromaDB storage directory (default: data/vectordb)"
    )
    parser.add_argument(
        "--collection",
        help="Collection name (default: derived from source_book)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing collection before inserting"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show collection statistics only"
    )
    
    args = parser.parse_args()
    
    # Initialize builder
    builder = VectorDBBuilder(db_path=args.db_path)
    
    # Stats mode
    if args.stats:
        if args.collection:
            builder.create_collection(args.collection)
            stats = builder.get_collection_stats()
            print("\n" + "=" * 60)
            print("COLLECTION STATISTICS")
            print("=" * 60)
            for key, value in stats.items():
                print(f"{key}: {value}")
        else:
            print("[ERROR] --collection required for --stats mode")
        return
    
    # Process file mode
    if not args.input_file:
        parser.print_help()
        print("\n[ERROR] input_file argument is required unless --stats is specified.")
        return
    
    # Process file
    stats = builder.process_file(
        args.input_file,
        collection_name=args.collection,
        reset=args.reset,
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("VECTOR DB BUILD COMPLETE")
    print("=" * 60)
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
