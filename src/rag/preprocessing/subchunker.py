# src/rag/preprocessing/subchunker.py
# src\rag\preprocessing\subchunker.py
#!/usr/bin/env python3
"""
Sub-chunking utility for breaking large chunks into smaller pieces.

Maintains context and parent-child relationships.
"""

from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import tiktoken


@dataclass
class SubChunk:
    """Sub-chunk with parent reference."""
    sub_chunk_id: str
    parent_chunk_id: str
    text: str
    start_offset: int
    end_offset: int
    token_count: int
    overlap_tokens: int


class SubChunker:
    """
    Create overlapping sub-chunks from large chunks.
    """
    
    def __init__(
        self,
        target_size: int = 300,
        max_size: int = 500,
        overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ):
        """
        Initialize sub-chunker.
        
        Args:
            target_size: Target tokens per sub-chunk
            max_size: Only sub-chunk if larger than this
            overlap: Overlap tokens between sub-chunks
            encoding_name: Tiktoken encoding name
        """
        self.target_size = target_size
        self.max_size = max_size
        self.overlap = overlap
        self.encoding = tiktoken.get_encoding(encoding_name)
    
    def should_subchunk(self, text: str, token_count: int) -> bool:
        """
        Determine if chunk should be sub-chunked.
        
        Args:
            text: Chunk text
            token_count: Token count
            
        Returns:
            True if should sub-chunk
        """
        return token_count > self.max_size
    
    def create_subchunks(
        self,
        chunk_id: str,
        text: str,
        metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Create sub-chunks from a large chunk.
        
        Args:
            chunk_id: Parent chunk ID
            text: Chunk text
            metadata: Chunk metadata
            
        Returns:
            List of sub-chunk dictionaries
        """
        # Tokenize
        tokens = self.encoding.encode(text)
        
        if len(tokens) <= self.max_size:
            # No need to sub-chunk
            return []
        
        sub_chunks = []
        sub_idx = 0
        
        # Create overlapping windows
        start = 0
        while start < len(tokens):
            end = min(start + self.target_size, len(tokens))
            
            # Extract sub-chunk tokens
            sub_tokens = tokens[start:end]
            sub_text = self.encoding.decode(sub_tokens)
            
            # Create sub-chunk
            sub_chunk = {
                "sub_chunk_id": f"{chunk_id}_sub{sub_idx}",
                "parent_chunk_id": chunk_id,
                "text": sub_text,
                "start_offset": start,
                "end_offset": end,
                "token_count": len(sub_tokens),
                "overlap_tokens": self.overlap if start > 0 else 0,
                "metadata": metadata.copy(),  # Inherit parent metadata
            }
            
            sub_chunks.append(sub_chunk)
            sub_idx += 1
            
            # Move window with overlap
            start = end - self.overlap
            
            # Prevent infinite loop
            if start >= len(tokens) - self.overlap:
                break
        
        print(f"[SUBCHUNK] Split {chunk_id} ({len(tokens)} tokens) into {len(sub_chunks)} sub-chunks")
        
        return sub_chunks
    
    def process_chunks(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Process all chunks and create sub-chunks where needed.
        
        Args:
            chunks: List of chunk dictionaries
            
        Returns:
            Combined list of original + sub-chunks
        """
        all_chunks = []
        subchunk_count = 0
        
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            text = chunk.get("text", "")
            token_count = chunk.get("token_count", 0)
            metadata = chunk.get("metadata", {})
            
            if self.should_subchunk(text, token_count):
                # Create sub-chunks
                sub_chunks = self.create_subchunks(chunk_id, text, metadata)
                all_chunks.extend(sub_chunks)
                subchunk_count += len(sub_chunks)
            else:
                # Keep original
                all_chunks.append(chunk)
        
        print(f"[INFO] Created {subchunk_count} sub-chunks from large chunks")
        print(f"[INFO] Total chunks: {len(all_chunks)}")
        
        return all_chunks


def main():
    """CLI for testing sub-chunker."""
    import json
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Sub-Chunker")
    parser.add_argument("input_file", help="Input JSON file with chunks")
    parser.add_argument("--output", help="Output file for sub-chunked data")
    parser.add_argument("--target-size", type=int, default=300, help="Target sub-chunk size")
    parser.add_argument("--max-size", type=int, default=500, help="Max size before sub-chunking")
    parser.add_argument("--overlap", type=int, default=50, help="Overlap tokens")
    
    args = parser.parse_args()
    
    # Load data
    with open(args.input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chunks = data.get("chunks", [])
    
    # Create sub-chunker
    subchunker = SubChunker(
        target_size=args.target_size,
        max_size=args.max_size,
        overlap=args.overlap,
    )
    
    # Process chunks
    processed_chunks = subchunker.process_chunks(chunks)
    
    # Save if output specified
    if args.output:
        data["chunks"] = processed_chunks
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Saved to: {args.output}")
    
    # Print stats
    print(f"\nOriginal chunks: {len(chunks)}")
    print(f"After sub-chunking: {len(processed_chunks)}")


if __name__ == "__main__":
    main()
