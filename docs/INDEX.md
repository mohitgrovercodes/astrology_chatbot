# NakshatraAI — Documentation Index

Welcome to the NakshatraAI documentation. This index links to all project docs.

---

## Core Documents

| Document | Audience | Description |
|---|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | All developers | System design, data flow, calculation engines, RAG pipeline, safety framework, and caching strategy |
| [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md) | Backend & AI engineers | Local setup, environment configuration, mobile app integration, extending predictions, RAG book management, cost tracking |
| [API_REFERENCE.md](./API_REFERENCE.md) | Mobile & backend integrators | All REST endpoints, authentication, request/response schemas, field names, rate limits, and error formats |

---

## Quick Navigation

### Getting Started
- [Local setup & installation](./DEVELOPER_GUIDE.md#-quick-start-local-setup)
- [Docker deployment](./DEVELOPER_GUIDE.md#docker-deployment)
- [Environment variables reference](./DEVELOPER_GUIDE.md#environment-variables-reference)

### API Integration
- [2-step chat protocol](./API_REFERENCE.md#chat-backend-integration--correct-protocol)
- [Authentication](./API_REFERENCE.md#authentication)
- [Field name reference (critical)](./API_REFERENCE.md#field-name-reference-critical--do-not-mix-up)
- [Rate limiting](./API_REFERENCE.md#rate-limiting)
- [Response format](./API_REFERENCE.md#response-format)
- [Conversation behavior notes](./API_REFERENCE.md#conversation-behavior-notes)

### Architecture
- [Data flow overview](./ARCHITECTURE.md#data-flow--lifecycle)
- [Vedic calculation engine](./ARCHITECTURE.md#vedic-engine-srcenginesvedic)
- [Western calculation engine](./ARCHITECTURE.md#western-engine-srcengineswestern)
- [RAG pipeline](./ARCHITECTURE.md#rag-pipeline)
- [LangGraph orchestrator](./ARCHITECTURE.md#orchestrator--validation)
- [Safety framework](./ARCHITECTURE.md#safety-framework)
- [Redis caching strategy](./ARCHITECTURE.md#caching--state-architecture)

### AI Engineering
- [Extending prediction logic](./DEVELOPER_GUIDE.md#-extending-prediction-logic-for-ai-engineers)
- [Managing RAG books](./DEVELOPER_GUIDE.md#-managing--expanding-the-rag-books)
- [Cost tracking](./DEVELOPER_GUIDE.md#-cost-tracking-system)

---

## Project Stats

| Metric | Value |
|---|---|
| Python source files | 103 (src/) · 148 total (incl. tests & scripts) |
| Orchestrator size | 7,000+ lines |
| Validation rules | 16,500+ (80 evaluated per live request) |
| RAG knowledge chunks | 14,000+ |
| Supported language codes | 13 (native + romanized Indian languages + English) |
| Safety gates | 3 (LLM-unified classifier) |
| Test files | 20 |
| LLM split | GPT-4o (synthesis/validation) + GPT-4o-mini (classification/safety) |
