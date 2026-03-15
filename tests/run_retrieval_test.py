# tests/run_retrieval_test.py
"""
Retrieval test using the production HybridRetriever path.

Run with conda env active and OPENAI_API_KEY set:
    conda activate venv/
    python tests/run_retrieval_test.py

No Redis required. Uses ChromaDB (data/vectordb) and OpenAI for embeddings/LLM.
Uses minimal imports (no orchestrator/swisseph) so it runs without full app deps.
"""

import os
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _get_vector_store_and_llm():
    """Build vector store and LLM with minimal deps (no orchestrator/config)."""
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings, ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    persist_dir = os.getenv("CHROMA_PERSIST_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "vectordb"))
    persist_dir = os.path.abspath(persist_dir)
    if not os.path.isdir(persist_dir):
        raise FileNotFoundError(f"ChromaDB directory not found: {persist_dir}")

    embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=api_key)
    vector_store = Chroma(
        collection_name="vedic_astrology_books_knowledge",
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )
    llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=api_key, temperature=0)
    return vector_store, llm


def main():
    from src.ai.hybrid_retriever import HybridRetriever

    print("=" * 60)
    print("RETRIEVAL TEST (Production HybridRetriever)")
    print("=" * 60)

    print("\n1. Loading vector store and LLM...")
    try:
        vector_store, llm = _get_vector_store_and_llm()
    except Exception as e:
        print(f"   [FAIL] {e}")
        print("   Ensure OPENAI_API_KEY is set and ChromaDB exists at data/vectordb (or set CHROMA_PERSIST_DIR).")
        return 1

    print("   [OK] Vector store and LLM ready.")

    print("\n2. Initializing HybridRetriever...")
    retriever = HybridRetriever(vector_store=vector_store, llm=llm, enable_memory=False)
    print("   [OK] HybridRetriever ready (memory disabled for this test).")

    test_queries = [
        ("When will I get married?", "RAG_WITH_CALCULATION", "interpretation"),
        ("What does Jupiter in 7th house mean?", "RAG_ONLY", "general"),
        ("Explain mahadasha and antardasha", "RAG_ONLY", "general"),
    ]

    print("\n3. Running retrieval for sample queries...")
    print("-" * 60)
    for query, intent, content_type in test_queries:
        print(f"\nQuery: \"{query}\"")
        print(f"Intent: {intent}  content_type: {content_type}")
        try:
            docs = retriever.retrieve(
                query=query,
                intent=intent,
                top_k=3,
                language="en",
                content_type=content_type,
            )
            print(f"   Retrieved: {len(docs)} chunks")
            for i, doc in enumerate(docs[:3], 1):
                src = (doc.metadata or {}).get("source_book", "?")
                snippet = (doc.page_content or "")[:120].replace("\n", " ")
                print(f"   [{i}] {src}: {snippet}...")
        except Exception as e:
            print(f"   [ERROR] {e}")
    print("-" * 60)
    print("\n[OK] Retrieval test finished.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
