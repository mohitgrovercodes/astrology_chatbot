#!/usr/bin/env python3
"""
Simplified Local Ingestion Script for Astrology Bot.

Reads '_embedded.json' files and pushes them directly into a 
local ChromaDB instance using config-defined paths.
"""

import os
import json
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.utils.config import get_config
from src.utils.logger import get_logger
import chromadb

logger = get_logger(__name__)

def ingest_local(
    input_dir: str,
    collection_name: Optional[str] = None,
    wipe: bool = False
):
    """
    Ingest embedded chunks from a directory into local ChromaDB.
    
    Args:
        input_dir: Directory containing processed _embedded.json files
        collection_name: Optional override for the target collection
        wipe: If True, deletes and recreates the collection
    """
    config = get_config()
    source_path = Path(input_dir)
    
    if not source_path.exists():
        logger.error(f"Source directory not found: {input_dir}")
        return

    # Initialize Chroma Client
    db_path = os.path.abspath(config.env.chroma_persist_dir)
    logger.info(f"Connecting to local ChromaDB at: {db_path}")
    
    client = chromadb.PersistentClient(path=db_path)
    
    target_collection = collection_name or config.rag.collection_name
    
    if wipe:
        try:
            client.delete_collection(name=target_collection)
            logger.warning(f"Collection '{target_collection}' WIPED.")
        except Exception:
            logger.info(f"Collection '{target_collection}' did not exist, starting fresh.")
            
    collection = client.get_or_create_collection(name=target_collection)
    logger.info(f"Active Collection: {target_collection} (Current chunks: {collection.count()})")

    # Locate files
    json_files = list(source_path.glob("**/*_embedded.json"))
    if not json_files:
        logger.warning(f"No '_embedded.json' files found in {input_dir}")
        return
        
    logger.info(f"Found {len(json_files)} embedded files. Starting ingestion...")

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
                logger.error(f"Skipping {file_path.name}: Unexpected structure (no 'chunks' key or list)")
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
                logger.info(f"OK: Ingested {len(ids)} chunks from {file_path.name}")

        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")

    logger.info("=" * 40)
    logger.info(f"INGESTION COMPLETE")
    logger.info(f"Total Chunks Added: {total_added}")
    logger.info(f"Final Collection Size: {collection.count()}")
    logger.info("=" * 40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local Ingestion for Astrology RAG")
    parser.add_argument("dir", help="Directory containing _embedded.json files")
    parser.add_argument("--collection", help="Override collection name")
    parser.add_argument("--wipe", action="store_true", help="Wipe existing collection")
    
    args = parser.parse_args()
    
    ingest_local(args.dir, args.collection, args.wipe)
