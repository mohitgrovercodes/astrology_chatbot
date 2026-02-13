# src\rag\ingest_local.py
#!/usr/bin/env python3
"""
Simplified Local Ingestion Script for Astrology Bot.

Reads '_embedded.json' files and pushes them directly into a 
local ChromaDB instance.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add project root to path for absolute imports
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

import chromadb

def ingest_local(
    input_dir: str,
    collection_name: Optional[str] = None,
    wipe: bool = False,
    chroma_dir: Optional[str] = None
):
    """
    Ingest embedded chunks from a directory into local ChromaDB.
    
    Args:
        input_dir: Directory containing processed _embedded.json files
        collection_name: Optional override for the target collection
        wipe: If True, deletes and recreates the collection
        chroma_dir: ChromaDB persist directory (default: ./chroma_db)
    """
    source_path = Path(input_dir)
    
    if not source_path.exists():
        print(f"[ERROR] Source directory not found: {input_dir}")
        return

    # Initialize Chroma Client
    if not chroma_dir:
        chroma_dir = os.environ.get("CHROMA_PERSIST_DIR", "./data/vectordb")
    
    db_path = os.path.abspath(chroma_dir)
    print(f"[INFO] Connecting to local ChromaDB at: {db_path}")
    
    
    client = chromadb.PersistentClient(path=db_path)
    
    if not collection_name:
        collection_name = os.environ.get("COLLECTION_NAME", "astrology_default")
    
    if wipe:
        try:
            client.delete_collection(name=collection_name)
            print(f"[WARN] Collection '{collection_name}' WIPED.")
        except Exception:
            print(f"[INFO] Collection '{collection_name}' did not exist, starting fresh.")
            
    collection = client.get_or_create_collection(name=collection_name)
    print(f"[INFO] Active Collection: {collection_name} (Current chunks: {collection.count()})")

    # Locate files
    json_files = list(source_path.glob("**/*_embedded.json"))
    if not json_files:
        print(f"[WARN] No '_embedded.json' files found in {input_dir}")
        return
        
    print(f"[INFO] Found {len(json_files)} embedded files. Starting ingestion...")


    total_added = 0
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both list and dict-with-chunks structure
            if isinstance(data, dict) and "chunks" in data:
                chunks = data["chunks"]
            elif isinstance(data, list):
                chunks = data
            else:
                print(f"[ERROR] Skipping {file_path.name}: Unexpected structure (no 'chunks' key or list)")
                continue

            ids, texts, embeddings, metadatas = [], [], [], []
            
            for c in chunks:
                ids.append(c['chunk_id'])
                # Use display_text for storage, but keep text_for_embedding in metadata if needed
                texts.append(c.get('display_text', c.get('text', '')))
                embeddings.append(c['embedding'])
                
                # Cleanup metadata
                meta = c.get('metadata', {}).copy()
                
                # Add basic info from chunk level
                meta['chunk_id'] = c['chunk_id']
                meta['unit_id'] = c.get('unit_id', '')
                meta['token_count'] = c.get('token_count', 0)
                meta['verse_sanskrit'] = c.get('verse_sanskrit', '')
                
                # Handle source pages
                if 'source_pages' in c:
                    meta['source_pages'] = ", ".join(map(str, c['source_pages']))
                
                # Flatten complex objects in metadata
                if 'entities' in meta:
                    for key, val in meta['entities'].items():
                        if isinstance(val, list):
                            meta[f"entity_{key}"] = ", ".join(val)
                    del meta['entities']
                
                # Ensure all metadata values are primitive for Chroma
                for key, val in list(meta.items()):
                    if val is None:
                        meta[key] = ""
                    elif isinstance(val, (list, dict)):
                        meta[key] = str(val)

                metadatas.append(meta)

            if ids:
                collection.upsert(
                    ids=ids,
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=metadatas
                )
                total_added += len(ids)
                print(f"[OK] Ingested {len(ids)} chunks from {file_path.name}")

        except Exception as e:
            print(f"[ERROR] Error processing {file_path.name}: {e}")

    print("=" * 40)
    print(f"INGESTION COMPLETE")
    print(f"Total Chunks Added: {total_added}")
    print(f"Final Collection Size: {collection.count()}")
    print("=" * 40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local Ingestion for Astrology RAG")
    parser.add_argument("dir", help="Directory containing _embedded.json files")
    parser.add_argument("--collection", help="Override collection name")
    parser.add_argument("--wipe", action="store_true", help="Wipe existing collection")
    parser.add_argument("--chroma-dir", help="ChromaDB persist directory")
    
    args = parser.parse_args()
    
    ingest_local(args.dir, args.collection, args.wipe, args.chroma_dir)

