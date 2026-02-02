# 🔄 PLATFORM HANDOFF DOCUMENT
## Astrology AI Chatbot Project - Cross-Platform Context Transfer

**Date:** {UPDATE_DATE}  
**Handoff From:** {SOURCE_PLATFORM}  
**Handoff To:** {TARGET_PLATFORM}  
**Current Phase:** {CURRENT_PHASE}  
**Overall Progress:** {PROGRESS_PERCENTAGE}%

---

## 📋 EXECUTIVE SUMMARY

### **Project Overview:**
A production-grade Astrology AI Chatbot supporting Vedic and Western astrology, designed for mobile app integration via REST API.

### **Core Architecture:**
```
CALCULATIONS = Deterministic VedicEngine (pyswisseph)
INTERPRETATIONS = LLM + RAG (knowledge-grounded)
ORCHESTRATION = LangGraph StateGraph (3-category routing)
```

### **Current State:**
- **Overall Progress:** {PROGRESS_PERCENTAGE}%
- **Current Phase:** {CURRENT_PHASE}
- **Status:** {CURRENT_STATUS}
- **Time to Launch:** {TIME_TO_LAUNCH}

---

## 🗂️ PROJECT STRUCTURE

### **Project Location:**
```
D:\AI\IMGProjects\astro_chatbot\astro_chatbot\
```

### **Key Directories:**
```
astro_chatbot/
├── src/
│   ├── engines/          # Deterministic calculations
│   │   ├── vedic/        # VedicEngine (pyswisseph)
│   │   ├── western/      # WesternEngine
│   │   └── core/         # Shared ephemeris
│   ├── ai/               # LLM components
│   │   ├── intent_classifier.py
│   │   ├── user_manager.py
│   │   └── hybrid_retriever.py
│   ├── orchestration/    # LangGraph orchestrator
│   ├── rag/              # RAG pipeline
│   └── tools/            # LangChain calculation tools
├── data/
│   ├── vectordb/         # Chroma vector store
│   └── pdfs/             # Source astrology books
├── docs/                 # Documentation
├── tests/                # Test suites
└── config/               # Configuration files
```

---

## 🎯 CURRENT PHASE STATUS

### **Phase Breakdown:**
```
Phase 1:  Foundation         [████████████████████] 100% ✅
Phase 2:  Engine Integration [████████████████████] 100% ✅
Phase 3:  RAG Pipeline       [████████████████████] 100% ✅
Phase 4:  LLM Integration    [████████████████████] 100% ✅
Phase 5:  Orchestration V1   [████████████████████] 100% ✅
Phase 5.5: Architecture V2   [████████████████████] {PHASE_5_5_PROGRESS}% {PHASE_5_5_STATUS}
Phase 6:  Safety & Guards    [████░░░░░░░░░░░░░░░░]  30% 
Phase 7:  API Layer          [░░░░░░░░░░░░░░░░░░░░]   0% 
Phase 8:  Testing            [░░░░░░░░░░░░░░░░░░░░]   0% 
Phase 9:  Fine-Tuning        [░░░░░░░░░░░░░░░░░░░░]   0% 
Phase 10: Deployment         [░░░░░░░░░░░░░░░░░░░░]   0% 
```

### **What's Working:**
{LIST_WORKING_COMPONENTS}

### **What's Pending:**
{LIST_PENDING_TASKS}

---

## 🔧 TECHNICAL DETAILS

### **Technology Stack:**
- **Language:** Python 3.11+
- **LLM:** Google Gemini 2.5 Flash
- **Embeddings:** OpenAI text-embedding-3-large
- **Vector DB:** ChromaDB
- **Orchestration:** LangGraph
- **Calculations:** pyswisseph (Swiss Ephemeris)
- **Database:** MongoDB (user profiles)

### **Key Dependencies:**
```
langchain==0.3.18
langgraph==0.2.60
langchain-google-genai==2.0.8
langchain-openai==0.3.0
langchain-chroma==0.2.1
pyswisseph==2.10.3.2
pymongo==4.11.0
```

### **Environment Variables:**
```bash
GOOGLE_API_KEY=<gemini-api-key>
OPENAI_API_KEY=<openai-api-key>
MONGODB_URI=<mongodb-connection-string>
```

---

## 📝 IMMEDIATE NEXT STEPS

### **Priority Tasks:**
{LIST_IMMEDIATE_TASKS}

### **Known Issues:**
{LIST_KNOWN_ISSUES}

### **Testing Status:**
{TESTING_STATUS}

---

## 🧪 HOW TO RUN TESTS

### **1. Calculation Tools Test:**
```bash
cd D:\AI\IMGProjects\astro_chatbot\astro_chatbot
.\venv\Scripts\activate.ps1
python src\tools\calculation_tools.py
```
**Expected:** All 3 tests pass (birth chart, dasha, transits)

### **2. Routing Test:**
```bash
python test_routing.py
```
**Expected:** 88-100% accuracy (16-18/18 passing)

### **3. Interactive Chatbot:**
```bash
python chatbot.py
```
**Expected:** Real-time conversation with personalized predictions

---

## 📚 KEY DOCUMENTATION

### **Core Documents:**
- `README.md` - Project overview and setup
- `ARCHITECTURE.md` - System architecture (v2)
- `PROJECT_STATUS_V3.md` - Detailed progress tracking
- `QUICK_REFERENCE.md` - Quick command reference

### **Technical Docs:**
- `docs/IMPLEMENTATION_GUIDE.md` - Implementation details
- `docs/VISION_EXTRACTION_PRODUCTION.md` - PDF extraction pipeline
- `docs/cost_logger_guide.md` - Cost tracking

---

## 🔑 CRITICAL CONTEXT

### **Design Decisions:**
1. **Deterministic Calculations:** All astronomical calculations use VedicEngine (pyswisseph), NOT LLMs
2. **3-Category Intent Routing:** CHITCHAT | NEEDS_CALCULATION | NEEDS_RAG
3. **RAG for Interpretation:** Classical astrology books provide grounded knowledge
4. **No Hallucinations:** Predictions based on real chart data + authoritative sources

### **Architecture Principles:**
- **Separation of Concerns:** Calculations ≠ Interpretations
- **Explainability:** Every prediction traceable to chart + knowledge source
- **Scalability:** Modular design for easy feature additions
- **Cost-Awareness:** Efficient LLM usage via caching and smart routing

---

## 🚨 IMPORTANT NOTES

### **What NOT to Do:**
- ❌ Don't use LLMs for astronomical calculations
- ❌ Don't mix placeholder data with real calculations
- ❌ Don't skip intent classification (causes routing errors)
- ❌ Don't modify VedicEngine without testing

### **What TO Do:**
- ✅ Always test calculations independently first
- ✅ Use RAG for all interpretation/prediction queries
- ✅ Maintain separation between calculations and interpretations
- ✅ Update documentation when making architectural changes

---

## 📞 HANDOFF CHECKLIST

Before switching platforms, ensure:
- [ ] All code changes committed to git
- [ ] Tests passing (calculation_tools.py, test_routing.py)
- [ ] Documentation updated (PROJECT_STATUS_V3.md)
- [ ] Environment variables documented
- [ ] Known issues listed
- [ ] Next steps clearly defined
- [ ] This handoff document updated

---

## 🎓 LEARNING RESOURCES

### **For Understanding the System:**
1. Read `ARCHITECTURE.md` for system design
2. Review `src/orchestration/orchestrator.py` for flow logic
3. Study `src/engines/vedic/vedic_engine.py` for calculations
4. Check `test_routing.py` for expected behavior

### **For Making Changes:**
1. Always run tests before and after changes
2. Update documentation concurrently with code
3. Follow existing patterns (don't reinvent)
4. Ask questions if architecture is unclear

---

**Last Updated:** {UPDATE_DATE}  
**Next Review:** {NEXT_REVIEW_DATE}

---

## 📝 HANDOFF NOTES (Session-Specific)

{ADD_SESSION_SPECIFIC_NOTES_HERE}
