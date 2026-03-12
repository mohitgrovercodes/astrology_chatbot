"""
Startup Profiling Script for NakshatraAI
Measures time taken by each initialization step.
"""
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

timings = []

def measure(label, func):
    """Measure and print time for a function."""
    print(f"\n{'='*60}")
    print(f"[PROFILE] Starting: {label}")
    start = time.perf_counter()
    try:
        result = func()
    except Exception as e:
        elapsed = time.perf_counter() - start
        timings.append((label, elapsed, f"ERROR: {e}"))
        print(f"[PROFILE] {label}: {elapsed:.2f}s (ERROR: {e})")
        return None
    elapsed = time.perf_counter() - start
    timings.append((label, elapsed, "OK"))
    print(f"[PROFILE] {label}: {elapsed:.2f}s")
    return result

# Step 1: Module imports
print("=" * 60)
print("[PROFILE] === STARTUP PROFILING ===")
print("=" * 60)

measure("Import orchestrator module", 
    lambda: __import__("src.orchestration.orchestrator", fromlist=["EnhancedLangGraphOrchestrator"]))

measure("Import safety classifier module", 
    lambda: __import__("src.safety.classifier", fromlist=["SafetyClassifier"]))

measure("Import SemanticRouter", 
    lambda: __import__("src.routing.semantic_router", fromlist=["SemanticRouter"]))

measure("Import Embedder", 
    lambda: __import__("src.rag.preprocessing.embedder", fromlist=["Embedder"]))

measure("Import LLMFactory", 
    lambda: __import__("src.llm.factory", fromlist=["LLMFactory"]))

# Step 2: Individual component init
from src.llm.factory import LLMFactory

measure("Create LLM (general)", lambda: LLMFactory.create(purpose="general"))
measure("Create LLM (classification)", lambda: LLMFactory.create(purpose="classification"))

# Step 3: Embedder init
from src.rag.preprocessing.embedder import Embedder
measure("Embedder.__init__", lambda: Embedder())

# Step 4: SemanticRouter
from src.routing.semantic_router import SemanticRouter

# Reset singleton for fresh measurement
SemanticRouter._instance = None

measure("SemanticRouter.__init__", lambda: SemanticRouter())

# Step 5: Measure individual add_route calls
router = SemanticRouter()

measure("add_route: greeting (16 examples)", lambda: router.add_route(
    name="greeting_test",
    examples=["hi", "hello", "hey", "namaste", "namaskaram", "vanakkam", "hola",
              "good morning", "good evening", "good afternoon", "howdy",
              "wassup", "sup", "yo", "greetings", "salaam"],
    metadata={"type": "greeting"}
))

measure("add_route: identity (11 examples)", lambda: router.add_route(
    name="identity_test",
    examples=["who are you", "what are you", "tell me about yourself",
              "what can you do", "introduce yourself",
              "what is your name", "what's your name",
              "kaun ho tum", "kya ho tum", "aap kaun hain",
              "aapka naam kya hai"],
    metadata={"type": "identity"}
))

# Step 6: Full orchestrator init (the real bottleneck)
from src.api.orchestrator_helper import get_orchestrator as _get_orch
# Reset singletons for measurement
import src.api.orchestrator_helper as oh
oh._orchestrator_instance = None

# Reset SemanticRouter singleton for fresh full measurement
SemanticRouter._instance = None

measure("Full get_orchestrator() init", _get_orch)

# Print summary
print("\n" + "=" * 60)
print("[PROFILE] === SUMMARY ===")
print("=" * 60)
total = sum(t[1] for t in timings)
for label, elapsed, status in sorted(timings, key=lambda x: -x[1]):
    pct = (elapsed / total * 100) if total > 0 else 0
    print(f"  {elapsed:7.2f}s ({pct:5.1f}%) | {status:5s} | {label}")
print(f"\n  TOTAL: {total:.2f}s")
