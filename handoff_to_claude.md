# Handoff to Claude

## 🚀 Project Status: Preprocessing Pipeline Modernized (89% Overall)

We have completed the modernization of the text preprocessing pipeline (Phases 2-6) and hardened the extraction pipeline (Phase 1) for **Vertex AI**.

### ✅ Recent Accomplishments (Critical for Context)

1.  **Vertex AI Integration & Auth Fixes**:
    *   **Prioritized Vertex AI**: `src/llm/factory.py` now prefers `ChatVertexAI` over AI Studio.
    *   **Fixed Authentication**: Removed `google_api_key` parameter when using Vertex AI (it relies on ADC properly now).
    *   **SDK Update**: Updated `src/rag/extraction/vision_extractor.py` to use `from google import genai` and set `GOOGLE_APPLICATION_CREDENTIALS`.
    *   **Configuration**: Initialized Vertex with Project ID `445806945384` and location `us-central1`.

2.  **LLM Factory Cleanup**:
    *   Removed `ChatAnthropic` and `ChatXAI` dependencies to solve import errors.
    *   Standardized on `gemini-2.5-flash` for all tasks (extraction and preprocessing).

3.  **Method Call Standardisation**:
    *   Fixed `AttributeError` in preprocessing modules (`structural_cleaner`, `page_analyzer`, `chunk_enricher`) by changing raw `.generate_content()` calls to LangChain's `.invoke()`.

### 🚧 Immediate Next Steps (To-Do)

The immediate goal is to finish **Phase 2: Pipeline Refactoring** from the `implementation_plan.md`.

1.  **Verification**: Confirm successful run of the pipeline with the new Vertex AI auth settings:
    ```bash
    python run_preprocessing_phases.py --input extraction_output/batch_result_pages_100-110.json --use-llm
    ```
2.  **Create Configuration Module**: Create `src/rag/preprocessing/config.py` to centralize settings (currently scattered in args and init methods).
3.  **Update Schemas**: Modify `src/rag/preprocessing/schemas.py` to natively accept the "Rich" JSON output from `VisionExtractor` (removing compatibility layers).
4.  **Parallelization**: Implement `ThreadPoolExecutor` in `src/rag/preprocessing/structural_cleaner.py` to match the performance of other modules.

### 🤖 Guidance for Claude (Instruction for the Next Agent)

When you take over, please prioritize these architectural principles and technical details:

1.  **Vertex AI Purity**:
    *   Do **NOT** use `google_api_key` for Vertex AI. The `LLMFactory` is configured to use ADC.
    *   The project ID is `445806945384` and location is `us-central1`.
    *   Always use `ChatVertexAI` from `langchain_google_vertexai`.

2.  **SDK Transition**:
    *   We are moving to the new `google.genai` SDK. In `vision_extractor.py`, use `from google import genai`.
    *   Be aware that `genai.configure` is from the old `google-generativeai` package. The new SDK uses a `Client` object, though for now, we've just updated the imports and env vars.

3.  **Pipeline Philosophy**:
    *   Transition from **File-based** to **In-memory**.
    *   The `implementation_plan.md` is your North Star. Follow the "Phase 2: Pipeline Refactoring" steps.

4.  **Astrology Context**:
    *   This is a RAG system for Vedic Astrology. Accuracy in Sanskrit extraction and preservation of verse numbers (`॥ 1.1 ॥`) is critical.
    *   Avoid hallucinations; if the OCR is bad, we retry with a better model (Gemini Pro).

### 🛠️ Key Context Files (Recommended Ingestion)

1.  **Handoff Documentation**:
    *   [handoff_to_claude.md](file:///C:/Users/mogr1/.gemini/antigravity/brain/36d443ce-b6ea-4404-84bb-535dba28f718/handoff_to_claude.md)
    *   [implementation_plan.md](file:///C:/Users/mogr1/.gemini/antigravity/brain/36d443ce-b6ea-4404-84bb-535dba28f718/implementation_plan.md)
    *   [task.md](file:///C:/Users/mogr1/.gemini/antigravity/brain/36d443ce-b6ea-4404-84bb-535dba28f718/task.md)

2.  **Core Codebase**:
    *   [factory.py](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/llm/factory.py)
    *   [vision_extractor.py](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/rag/extraction/vision_extractor.py)
    *   [pipeline.py](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/rag/preprocessing/pipeline.py)
    *   [schemas.py](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/rag/preprocessing/schemas.py)
