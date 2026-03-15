from langchain_core.documents import Document

from src.ai.hybrid_retriever import HybridRetriever


class _FakeVectorStore:
    def similarity_search(self, query, k=4, filter=None):
        return [
            Document(page_content='Jupiter in 7th house supports wise partnerships.', metadata={'source_book': 'BPHS', 'chapter': 'House effects'}),
            Document(page_content='Saturn in 10th house gives disciplined career growth.', metadata={'source_book': 'Saravali', 'chapter': 'Career'}),
        ][:k]


class _FakeLLM:
    def invoke(self, prompt):
        class _Resp:
            content = 'Classical passage about Jupiter and marriage.'
        return _Resp()


class _FakeMemory:
    def retrieve_memories(self, user_id, query, k=2):
        return [{'content': 'User previously asked about marriage timing.', 'metadata': {'user_id': user_id}}]


class _FakeReranker:
    def rerank(self, query, chunks, top_k=None, content_type=None):
        # deterministic reorder by text length to emulate rerank behavior
        out = sorted(chunks, key=lambda c: len(c.text), reverse=True)
        return out[:top_k] if top_k else out


def test_hybrid_retriever_injects_memory_and_dedupes(monkeypatch):
    retriever = HybridRetriever(vector_store=_FakeVectorStore(), llm=_FakeLLM(), enable_memory=False)
    retriever.memory_retriever = _FakeMemory()
    retriever.reranker = None

    docs = retriever.retrieve(query='Will I marry?', intent='RAG_WITH_CALCULATION', top_k=3, user_id='u1', content_type='interpretation')

    assert len(docs) >= 2
    assert any(d.metadata.get('memory_hit') for d in docs)


def test_hybrid_retriever_uses_reranker_when_available(monkeypatch):
    retriever = HybridRetriever(vector_store=_FakeVectorStore(), llm=_FakeLLM(), enable_memory=False)
    retriever.reranker = _FakeReranker()

    docs = retriever.retrieve(query='Career and marriage', intent='RAG_WITH_CALCULATION', top_k=1, content_type='interpretation')
    assert len(docs) == 1


def test_retrieve_as_chunks_returns_chunk_shape():
    retriever = HybridRetriever(vector_store=_FakeVectorStore(), llm=_FakeLLM(), enable_memory=False)
    chunks = retriever.retrieve_as_chunks(query='Explain Jupiter', intent='RAG_ONLY', top_k=1)
    assert len(chunks) == 1
    assert hasattr(chunks[0], 'chunk_id')
    assert hasattr(chunks[0], 'display_text')
