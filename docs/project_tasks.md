# Project Tasks & Roadmap

**Status**: Feb 6, 2026
**Derived from**: Antigravity Brain Task Checklist

## Phase 9: UX Enhancements [x]
- [x] Replace source numbers with book/author citations
- [x] Implement two-tier response flow (brief → detailed on request)
- [x] Enable automatic language script mirroring
- [x] Enable Romanized script support (Hinglish/Tanglish)
- [x] **BUGFIX**: Added missing `get_language_enforcement` to `localization.py`
- [x] **OPTIMIZATION**: Expanded Hinglish markers (22 → 46 words)
- [x] **OPTIMIZATION**: Adjusted detection threshold for short queries
- [x] **Romanized Script Support**: Enforce Latin script for "Hinglish" (hi-lat) inputs
- [x] **Persona Logic**: Disable auto-detect and rely on User Profile for system selection

## Phase 10: Constitutional AI & Guardrails [x]
- [x] **Constitution**: Create `src/safety/constitution.py` with the 4 Immutable Rules
- [x] **Orchestrator**: Inject Constitution into System Prompts associated with persona
- [x] **Critic Node**: Implement `_validate_response_node` in LangGraph (Verification Loop)
- [x] **Jailbreak Guard**: Enhance `QueryAnalyzer` to catch adversarial inputs
- [x] **Fact Checker**: Implement basic consistency check (Data vs Text)
- [x] **Testing**: Verify refusal of death predictions and fake math

## Phase 10.5: Advanced Safety Migration [x]
- [x] **Analysis**: Review `new_safety_framework` logic and templates
- [x] **Migration**: Replace `src/safety` with new classifier/models/templates
- [x] **Integration**: Update `orchestrator.py` to use `SafetyClassifier` (Multi-Gate)
- [x] **UX**: Implement automatic query reframing and disclaimer injection
- [x] **Verification**: Run comprehensive safety test suite

## Phase 11: Artificial Intelligence (Semantic Routing) [x]
- [x] **Setup**: Install `sentence-transformers` & create `src/routing`
- [x] **Core**: Build `SemanticRouter` class (Embedding + Cosine Similarity)
- [x] **Routes**: Define canonical examples for `chitchat`, `safety`, `astrology`
- [x] **Integration**: Replace Regex in `SafetyClassifier` with Semantic Route
- [x] **Integration**: Replace `_is_fast_chitchat` in Orchestrator with Semantic Route
- [x] **Verification**: Benchmark latency and accuracy (8/8 pass)

## Phase 12: Deployment (Coming Soon)
- [ ] API Wrapper (FastAPI)
- [ ] Docker Containerization
- [ ] Cloud Deployment
