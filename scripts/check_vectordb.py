# check_vectordb.py - Diagnose BM25 Issue

import os
from dotenv import load_dotenv

load_dotenv()

print("="*80)
print("VECTOR DATABASE DIAGNOSTIC")
print("="*80)
print()

print(f"Current directory: {os.getcwd()}")
print(f"Data directory exists: {os.path.exists('data/vectordb')}")
print()

try:
    from langchain_chroma import Chroma
    from langchain_google_vertexai import VertexAIEmbeddings

    print("Initializing embeddings...")
    embeddings = VertexAIEmbeddings(model_name="gemini-embedding-001", output_dimensionality=1536)
    
    print("Connecting to vector store...")
    vector_store = Chroma(
        collection_name="vedic_astrology_books_knowledge",
        embedding_function=embeddings,
        persist_directory="./data/vectordb"
    )
    
    # Get document count
    count = vector_store._collection.count()
    print(f"\n[OK] Collection: vedic_astrology_books_knowledge")
    print(f"   Documents: {count}")
    
    if count == 0:
        print("\n[FAIL] PROBLEM: Collection is EMPTY!")
        print("\nPossible causes:")
        print("1. Vector database was never populated")
        print("2. Wrong collection name")
        print("3. Wrong persist directory path")
        print("4. Collection was deleted/corrupted")
        
        # Try to list all collections
        print("\nChecking for other collections...")
        import chromadb
        client = chromadb.PersistentClient(path="./data/vectordb")
        collections = client.list_collections()
        
        print(f"\nAvailable collections: {len(collections)}")
        for col in collections:
            print(f"  - {col.name}: {col.count()} documents")
    else:
        print(f"\n[OK] Vector database is healthy with {count} documents")
        
        # Test retrieval
        print("\nTesting retrieval...")
        results = vector_store.similarity_search("marriage timing", k=3)
        print(f"[OK] Retrieved {len(results)} documents for test query")
        if results:
            print(f"   First result preview: {results[0].page_content[:100]}...")
    
except Exception as e:
    print(f"\n[FAIL] ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("DIAGNOSIS COMPLETE")
print("="*80)