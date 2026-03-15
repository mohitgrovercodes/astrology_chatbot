from src.ai.prompt_builder import PromptBuilder


class _Chunk:
    def __init__(self, text, metadata):
        self.page_content = text
        self.metadata = metadata


def test_prompt_builder_formats_knowledge_with_citations():
    pb = PromptBuilder()
    chunks = [
        _Chunk(
            'Jupiter in kendra houses enhances benefic outcomes according to classics.',
            {'source_book': 'BPHS', 'chapter': 'Chapter 15', 'verse_number': '3'}
        )
    ]

    prompt = pb.build_prompt(
        query='What does Jupiter in 7th house mean?',
        intent='RAG_ONLY',
        user_profile={'name': 'Test', 'preferred_system': 'vedic'},
        knowledge_chunks=chunks,
        language='en'
    )

    assert 'GROUNDING RULES' in prompt
    assert 'BPHS' in prompt
    assert 'Chapter 15' in prompt
