
import sys
import argparse
from src.rag.retriever import AstrologyRetriever

def debug_retrieval():
    parser = argparse.ArgumentParser(description="Debug RAG Retrieval (No LLM)")
    parser.add_argument("query", help="The question to test")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to fetch")
    parser.add_argument("--hybrid", action="store_true", help="Use Hybrid Search (BM25 + Vector)")
    parser.add_argument("--rerank", action="store_true", help="Apply Cross-Encoder Reranking")
    parser.add_argument("--hyde", action="store_true", help="Use HyDE (Hypothetical Document Embedding)")
    parser.add_argument("--collection", help="Specific collection name to search")
    
    args = parser.parse_args()
    
    print(f"\n🔍 Debugging Retrieval for: '{args.query}'")
    print(f"⚙️  Settings: Top-K={args.top_k}, Hybrid={args.hybrid}, Rerank={args.rerank}, HyDE={args.hyde}")
    print("-" * 60)
    
    # Initialize Retriever
    try:
        # 1. Try to guess collection if not provided
        collection_to_use = args.collection
        if not collection_to_use:
            try:
                import chromadb
                client = chromadb.PersistentClient(path="data/vectordb")
                cols = client.list_collections()
                if cols:
                    # Pick the most recently created or first one
                    collection_to_use = cols[0].name
                    print(f"💡 Auto-detected collection: '{collection_to_use}'")
            except Exception:
                pass # Fallback to retriever default

        retriever = AstrologyRetriever(collection_name=collection_to_use)
        
        if not retriever.collection:
            print(f"❌ Error: Collection '{retriever.collection_name}' not found.")
            print("Run pipeline.py first or check --collection argument.")
            return
    except Exception as e:
        print(f"❌ Initialization Error: {e}")
        return

    # Execute Search
    top_k_fetch = args.top_k * 3 if args.rerank else args.top_k # Fetch more candidates if reranking
    
    if args.hyde:
        print(f"🚀 Running HyDE Search (fetching {top_k_fetch})...")
        print("   (Generating hypothetical answer first using LLM...)")
        try:
            from src.llm.factory import create_llm
            llm = create_llm(provider="google", model="gemini-2.5-flash") # Use Flash for speed
            results = retriever.retrieve_with_advanced_hyde(args.query, top_k=top_k_fetch, llm=llm)
        except Exception as e:
            print(f"❌ HyDE Error: {e}")
            return
    elif args.hybrid:
        print(f"🚀 Running Hybrid Search (fetching {top_k_fetch})...")
        results = retriever.retrieve_hybrid(args.query, top_k=top_k_fetch)
    else:
        print(f"🚀 Running Vector Search (fetching {top_k_fetch})...")
        results = retriever.retrieve(args.query, top_k=top_k_fetch)
        
    print(f"✅ Found {len(results)} chunks (before reranking).\n")
    
    # Rerank if enabled
    if args.rerank:
        print("🔝 Applying Cross-Encoder Reranking...")
        try:
            from src.rag.reranker import Reranker
            reranker = Reranker()
            results = reranker.rerank(args.query, results, top_k=args.top_k)
            print(f"✅ Reranked to top {len(results)} chunks.\n")
        except ImportError:
            print("❌ Error: sentence-transformers not installed. Run: pip install sentence-transformers")
        except Exception as e:
            print(f"❌ Reranking Error: {e}")

    # Display Results
    
    # Display Results
    for i, chunk in enumerate(results, 1):
        print(f"📄 CHUNK {i} (Score: {chunk.score:.4f})")
        print(f"   Source: {chunk.metadata.get('source_book', 'Unknown')}")
        if chunk.metadata.get('chapter'):
            print(f"   Chapter: {chunk.metadata['chapter']}")
        print(f"   Text Snippet: {chunk.display_text[:200]}...") # Show first 200 chars
        print("-" * 40)

if __name__ == "__main__":
    debug_retrieval()
