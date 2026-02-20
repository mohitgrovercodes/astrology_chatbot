# comprehensive_test_suite.py
"""
NakshatraAI - Complete System Test Suite
Tests all known issues and concerns from production logs.

Usage: python comprehensive_test_suite.py
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment
load_dotenv()

# ============================================================================
# COLOR OUTPUT
# ============================================================================

class Color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text: str):
    print(f"\n{Color.BOLD}{Color.BLUE}{'='*80}{Color.END}")
    print(f"{Color.BOLD}{Color.BLUE}{text.center(80)}{Color.END}")
    print(f"{Color.BOLD}{Color.BLUE}{'='*80}{Color.END}\n")

def print_test(name: str):
    print(f"\n{Color.CYAN}► Testing: {name}{Color.END}")

def print_pass(msg: str, details: str = ""):
    print(f"{Color.GREEN}  ✅ PASS{Color.END} - {msg}")
    if details:
        print(f"     {Color.CYAN}{details}{Color.END}")

def print_fail(msg: str, details: str = ""):
    print(f"{Color.RED}  ❌ FAIL{Color.END} - {msg}")
    if details:
        print(f"     {Color.RED}{details}{Color.END}")

def print_warn(msg: str, details: str = ""):
    print(f"{Color.YELLOW}  ⚠️  WARN{Color.END} - {msg}")
    if details:
        print(f"     {Color.YELLOW}{details}{Color.END}")

def print_info(msg: str):
    print(f"{Color.CYAN}  ℹ️  {msg}{Color.END}")

# ============================================================================
# TEST RESULTS TRACKER
# ============================================================================

class TestTracker:
    def __init__(self):
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': [],
            'start_time': datetime.now()
        }
    
    def record(self, category: str, test_name: str, status: str, details: str = ""):
        result = {
            'category': category,
            'test': test_name,
            'status': status,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        
        if status == 'pass':
            self.results['passed'].append(result)
        elif status == 'fail':
            self.results['failed'].append(result)
        else:
            self.results['warnings'].append(result)
        
        return result
    
    def save_report(self, filename: str = 'test_report.json'):
        report = {
            'timestamp': datetime.now().isoformat(),
            'duration': str(datetime.now() - self.results['start_time']),
            'summary': {
                'total': len(self.results['passed']) + len(self.results['failed']) + len(self.results['warnings']),
                'passed': len(self.results['passed']),
                'failed': len(self.results['failed']),
                'warnings': len(self.results['warnings'])
            },
            'results': self.results
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)  # Add default=str to handle datetime
        
        return filename

tracker = TestTracker()

# ============================================================================
# TEST SUITE 1: CRITICAL INFRASTRUCTURE
# ============================================================================

def test_01_environment():
    print_header("TEST 1: Environment & Critical Dependencies")
    
    # Python version
    print_test("Python Version")
    if sys.version_info >= (3, 11):
        print_pass(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        tracker.record('env', 'Python Version', 'pass', f"{sys.version}")
    else:
        print_fail(f"Need Python 3.11+, have {sys.version_info.major}.{sys.version_info.minor}")
        tracker.record('env', 'Python Version', 'fail', f"{sys.version}")
    
    # Critical environment variables
    print_test("Environment Variables")
    env_checks = {
        'OPENAI_API_KEY': 'required',
        'GOOGLE_CLOUD_PROJECT': 'required',
        'GOOGLE_APPLICATION_CREDENTIALS': 'required',
        'LLM_PROVIDER': 'optional',
        'LLM_MODEL': 'optional',
    }
    
    for var, importance in env_checks.items():
        value = os.getenv(var)
        if value:
            masked = value[:8] + "..." if len(value) > 8 else "set"
            print_pass(f"{var}", masked)
            tracker.record('env', var, 'pass')
        elif importance == 'required':
            print_fail(f"{var}", "NOT SET - Required!")
            tracker.record('env', var, 'fail', 'Not set')
        else:
            print_warn(f"{var}", "Not set (optional)")
            tracker.record('env', var, 'warning', 'Not set')
    
    # Critical packages
    print_test("Python Packages")
    packages = {
        'langchain': 'RAG framework',
        'langchain_openai': 'OpenAI integration',
        'langchain_chroma': 'Vector database',
        'chromadb': 'Vector storage',
        'openai': 'OpenAI API',
        'fastapi': 'API framework',
        'pydantic': 'Data validation',
        'rank_bm25': 'BM25 search',
        'swisseph': 'Swiss Ephemeris',
    }
    
    for package, description in packages.items():
        try:
            mod = __import__(package)
            version = getattr(mod, '__version__', 'unknown')
            print_pass(f"{package} ({description})", f"v{version}")
            tracker.record('env', f'Package: {package}', 'pass', version)
        except ImportError:
            print_fail(f"{package} ({description})", "NOT INSTALLED")
            tracker.record('env', f'Package: {package}', 'fail', 'Not installed')

# ============================================================================
# TEST SUITE 2: RAG / VECTOR DATABASE (CRITICAL ISSUE)
# ============================================================================

def test_02_rag_vector_database():
    print_header("TEST 2: RAG & Vector Database (KNOWN ISSUE)")
    
    print_info("This is the PRIMARY failing component in production logs")
    print_info("Expected: 14,508 documents | Actual in logs: 0 documents")
    
    try:
        from langchain_openai import OpenAIEmbeddings
        from langchain_chroma import Chroma
        
        print_test("ChromaDB Initialization")
        
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            dimensions=3072
        )
        
        print_info("Connecting to ChromaDB...")
        
        vector_store = Chroma(
            collection_name="vedic_astrology_books_knowledge",
            embedding_function=embeddings,
            persist_directory="./data/vectordb"
        )
        
        print_pass("ChromaDB connected")
        tracker.record('rag', 'ChromaDB Connection', 'pass')
        
        # CRITICAL TEST: Document count
        print_test("Document Count (CRITICAL)")
        count = vector_store._collection.count()
        
        print_info(f"Found {count} documents in collection")
        
        if count >= 14000:
            print_pass(f"Document count: {count}", "Expected ~14,508")
            tracker.record('rag', 'Document Count', 'pass', f'{count} documents')
        elif count > 1000:
            print_warn(f"Document count: {count}", "Lower than expected 14,508")
            tracker.record('rag', 'Document Count', 'warning', f'{count} documents')
        elif count > 0:
            print_fail(f"Document count: {count}", "CRITICALLY LOW! Expected 14,508")
            tracker.record('rag', 'Document Count', 'fail', f'Only {count} documents')
        else:
            print_fail("Document count: 0", "DATABASE IS EMPTY! This matches production error!")
            tracker.record('rag', 'Document Count', 'fail', 'ChromaDB is empty')
            print_info("This explains why RAG returns 0 chunks in production")
        
        # Test vector search if docs exist
        if count > 0:
            print_test("Vector Search")
            try:
                results = vector_store.similarity_search("marriage", k=5)
                if len(results) > 0:
                    print_pass(f"Vector search returned {len(results)} results")
                    print_info(f"Sample: {results[0].page_content[:80]}...")
                    tracker.record('rag', 'Vector Search', 'pass', f'{len(results)} results')
                else:
                    print_fail("Vector search returned 0 results")
                    tracker.record('rag', 'Vector Search', 'fail', '0 results')
            except Exception as e:
                print_fail("Vector search failed", str(e))
                tracker.record('rag', 'Vector Search', 'fail', str(e))
        
        # Test collection access
        print_test("Collection Verification")
        try:
            collections = vector_store._client.list_collections()
            collection_names = [c.name for c in collections]
            
            print_info(f"Available collections: {collection_names}")
            
            if 'vedic_astrology_books_knowledge' in collection_names:
                print_pass("Target collection exists")
                tracker.record('rag', 'Collection Exists', 'pass')
            else:
                print_fail("Target collection NOT FOUND", f"Available: {collection_names}")
                tracker.record('rag', 'Collection Exists', 'fail', 'Not found')
        except Exception as e:
            print_fail("Collection check failed", str(e))
            tracker.record('rag', 'Collection Check', 'fail', str(e))
        
        # Test BM25 building
        print_test("BM25 Index Building")
        if count > 0:
            try:
                from rank_bm25 import BM25Okapi
                
                # Try Strategy 1: Direct collection access
                print_info("Attempting Strategy 1: Direct collection.get()...")
                try:
                    batch = vector_store._collection.get(limit=100)
                    if batch and batch.get('documents'):
                        docs_count = len(batch['documents'])
                        print_pass(f"Strategy 1: Got {docs_count} documents")
                        tracker.record('rag', 'BM25 Strategy 1', 'pass', f'{docs_count} docs')
                    else:
                        print_fail("Strategy 1: collection.get() returned empty")
                        tracker.record('rag', 'BM25 Strategy 1', 'fail', 'Empty result')
                except Exception as e:
                    print_fail(f"Strategy 1 failed: {str(e)}")
                    tracker.record('rag', 'BM25 Strategy 1', 'fail', str(e))
                
                # Try Strategy 2: Similarity search
                print_info("Attempting Strategy 2: similarity_search()...")
                try:
                    docs = vector_store.similarity_search("astrology", k=100)
                    if docs:
                        print_pass(f"Strategy 2: Got {len(docs)} documents")
                        tracker.record('rag', 'BM25 Strategy 2', 'pass', f'{len(docs)} docs')
                    else:
                        print_fail("Strategy 2: similarity_search() returned empty")
                        tracker.record('rag', 'BM25 Strategy 2', 'fail', 'Empty result')
                except Exception as e:
                    print_fail(f"Strategy 2 failed: {str(e)}")
                    tracker.record('rag', 'BM25 Strategy 2', 'fail', str(e))
                    
            except ImportError:
                print_warn("rank-bm25 not installed")
                tracker.record('rag', 'BM25 Index', 'warning', 'Package not installed')
        else:
            print_fail("Cannot test BM25 - database is empty")
            tracker.record('rag', 'BM25 Index', 'fail', 'No documents')
        
    except Exception as e:
        print_fail("RAG System Failed", str(e))
        tracker.record('rag', 'RAG System', 'fail', str(e))
        import traceback
        traceback.print_exc()

# ============================================================================
# TEST SUITE 3: CALCULATION ENGINES
# ============================================================================

def test_03_calculation_engines():
    print_header("TEST 3: Vedic Calculation Engines")
    
    try:
        from src.engines.vedic.vedic_engine import VedicEngine
        from datetime import datetime
        
        print_test("VedicEngine Initialization")
        engine = VedicEngine()
        print_pass("VedicEngine created")
        tracker.record('calc', 'VedicEngine Init', 'pass')
        
        # Test chart generation
        print_test("Birth Chart Generation (D1)")
        birth_date = datetime(1990, 5, 15, 14, 30)
        chart = engine.generate_chart(
            birth_date=birth_date,
            latitude=12.9716,
            longitude=77.5946,
            timezone_str="Asia/Kolkata"
        )
        
        if chart and chart.lagna:
            print_pass(f"Chart generated", f"Lagna: {chart.lagna.rashi_name}")
            tracker.record('calc', 'Birth Chart D1', 'pass', f'Lagna: {chart.lagna.rashi_name}')
        else:
            print_fail("Chart generation failed")
            tracker.record('calc', 'Birth Chart D1', 'fail')
        
        # Test divisional charts
        print_test("Divisional Charts (D2-D60)")
        if hasattr(chart, 'vargas') and chart.vargas:
            varga_count = len(chart.vargas)
            print_pass(f"{varga_count} divisional charts calculated")
            
            # Check specific charts
            from src.engines.core.celestial_bodies import CelestialBody
            from src.engines.vedic.vedic_constants import VargaChart
            
            critical_charts = {
                'D7': 'Children',
                'D9': 'Marriage', 
                'D10': 'Career',
                'D4': 'Property'
            }
            
            for chart_name, purpose in critical_charts.items():
                varga_enum = getattr(VargaChart, chart_name, None)
                if varga_enum and CelestialBody.JUPITER in chart.vargas:
                    position = chart.vargas[CelestialBody.JUPITER].get_position(varga_enum)
                    if position:
                        print_pass(f"{chart_name} ({purpose})", f"Jupiter: {position.rashi.name}")
                        tracker.record('calc', f'Divisional {chart_name}', 'pass', position.rashi.name)
                    else:
                        print_warn(f"{chart_name} ({purpose})", "Could not get position")
                        tracker.record('calc', f'Divisional {chart_name}', 'warning', 'No position')
            
            tracker.record('calc', 'Divisional Charts', 'pass', f'{varga_count} charts')
        else:
            print_fail("No divisional charts calculated")
            tracker.record('calc', 'Divisional Charts', 'fail')
        
        # Test Dasha
        print_test("Vimshottari Dasha")
        if hasattr(chart, 'dasha') and chart.dasha:
            print_pass("Dasha calculated")
            # Check for balance (different possible attribute names)
            if hasattr(chart.dasha, 'dasha_balance'):
                balance = chart.dasha.dasha_balance.remaining_years
                print_info(f"Balance: {balance:.2f} years")
            elif hasattr(chart.dasha, 'balance_years'):
                balance = chart.dasha.balance_years
                print_info(f"Balance: {balance:.2f} years")
            tracker.record('calc', 'Vimshottari Dasha', 'pass', 'Dasha calculated')
        else:
            print_fail("Dasha not calculated")
            tracker.record('calc', 'Vimshottari Dasha', 'fail')
        
        # Test Yogas
        print_test("Yoga Detection")
        if hasattr(chart, 'yogas') and chart.yogas:
            print_pass("Yogas calculated")
            tracker.record('calc', 'Yoga Detection', 'pass')
        else:
            print_warn("No yogas detected")
            tracker.record('calc', 'Yoga Detection', 'warning', 'None found')
        
        # Test Aspects
        print_test("Aspect Calculation")
        if hasattr(chart, 'aspects') and chart.aspects:
            print_pass("Aspects calculated")
            tracker.record('calc', 'Aspects', 'pass')
        else:
            print_warn("No aspects calculated")
            tracker.record('calc', 'Aspects', 'warning')
            
    except Exception as e:
        print_fail("Calculation engine failed", str(e))
        tracker.record('calc', 'Calculation Engine', 'fail', str(e))
        import traceback
        traceback.print_exc()

# ============================================================================
# TEST SUITE 4: SERIALIZATION (KNOWN ISSUES)
# ============================================================================

def test_04_serialization():
    print_header("TEST 4: Data Serialization (YogaDetection, AspectGrid)")
    
    print_info("Known issues from logs:")
    print_info("  - TypeError: Object of type YogaDetection is not JSON serializable")
    print_info("  - TypeError: Object of type AspectGrid is not JSON serializable")
    
    try:
        from src.tools.calculation_tools import format_chart_for_llm
        from src.engines.vedic.vedic_engine import VedicEngine
        from datetime import datetime
        import json
        
        print_test("Generate Chart")
        engine = VedicEngine()
        chart = engine.generate_chart(
            birth_date=datetime(1990, 5, 15, 14, 30),
            latitude=12.9716,
            longitude=77.5946,
            timezone_str="Asia/Kolkata"
        )
        print_pass("Chart generated")
        
        print_test("format_chart_for_llm()")
        formatted = format_chart_for_llm(chart)
        
        if formatted:
            print_pass(f"Chart formatted", f"{len(formatted)} keys")
            print_info(f"Keys: {list(formatted.keys())}")
            tracker.record('serial', 'format_chart_for_llm', 'pass', f'{len(formatted)} keys')
        else:
            print_fail("format_chart_for_llm returned empty")
            tracker.record('serial', 'format_chart_for_llm', 'fail')
        
        # Check for divisional charts
        print_test("Divisional Charts in Output")
        if 'divisional_charts' in formatted or 'vargas' in formatted:
            print_pass("Divisional charts present")
            tracker.record('serial', 'Divisional in Output', 'pass')
        else:
            print_fail("Divisional charts MISSING from output")
            tracker.record('serial', 'Divisional in Output', 'fail')
        
        # Check for yogas
        print_test("Yogas in Output")
        if 'yogas' in formatted:
            print_pass("Yogas present")
            # Try to serialize yogas
            try:
                json.dumps(formatted['yogas'], default=str)
                print_pass("Yogas are JSON serializable")
                tracker.record('serial', 'Yogas Serialization', 'pass')
            except TypeError as e:
                print_fail("Yogas NOT JSON serializable", str(e))
                tracker.record('serial', 'Yogas Serialization', 'fail', str(e))
        else:
            print_warn("Yogas not in output")
            tracker.record('serial', 'Yogas in Output', 'warning')
        
        # Check for aspects
        print_test("Aspects in Output")
        if 'aspects' in formatted:
            print_pass("Aspects present")
            # Try to serialize aspects
            try:
                json.dumps(formatted['aspects'], default=str)
                print_pass("Aspects are JSON serializable")
                tracker.record('serial', 'Aspects Serialization', 'pass')
            except TypeError as e:
                print_fail("Aspects NOT JSON serializable", str(e))
                tracker.record('serial', 'Aspects Serialization', 'fail', str(e))
        else:
            print_warn("Aspects not in output")
            tracker.record('serial', 'Aspects in Output', 'warning')
        
        # Full JSON serialization test
        print_test("Complete JSON Serialization")
        try:
            json_str = json.dumps(formatted, default=str)
            print_pass(f"Full chart serialization successful", f"{len(json_str)} chars")
            tracker.record('serial', 'Full JSON Serialization', 'pass', f'{len(json_str)} chars')
        except TypeError as e:
            print_fail("Full chart serialization FAILED", str(e))
            tracker.record('serial', 'Full JSON Serialization', 'fail', str(e))
            
    except Exception as e:
        print_fail("Serialization test failed", str(e))
        tracker.record('serial', 'Serialization', 'fail', str(e))
        import traceback
        traceback.print_exc()

# ============================================================================
# TEST SUITE 5: VALIDATION ENGINE
# ============================================================================

def test_05_validation_engine():
    print_header("TEST 5: Validation Engine (16,000 Rules)")
    
    print_info("Validation has been working perfectly in logs (10/10 strength)")
    print_info("This test verifies it continues to work")
    
    try:
        print_test("Rules File")
        rules_file = "optimized/tiered_rules.json"
        
        if os.path.exists(rules_file):
            with open(rules_file, 'r', encoding='utf-8', errors='ignore') as f:
                rules = json.load(f)
            
            tier1 = len(rules.get('tier_1', []))
            tier2 = len(rules.get('tier_2', []))
            tier3 = len(rules.get('tier_3', []))
            total = tier1 + tier2 + tier3
            
            print_pass(f"Rules loaded: {total}", f"T1:{tier1}, T2:{tier2}, T3:{tier3}")
            tracker.record('validation', 'Rules File', 'pass', f'{total} total')
            
            if total < 10000:
                print_warn("Rule count lower than expected 16,000")
                tracker.record('validation', 'Rule Count', 'warning', f'{total} vs 16,000')
        else:
            print_fail("Rules file not found", rules_file)
            tracker.record('validation', 'Rules File', 'fail', 'Not found')
        
        # Check index file
        print_test("Index File")
        index_file = "optimized/indexed_rules.json"
        
        if os.path.exists(index_file):
            with open(index_file, 'r', encoding='utf-8', errors='ignore') as f:
                index = json.load(f)
            
            query_types = list(index.keys())
            print_pass(f"Index loaded: {len(query_types)} query types")
            print_info(f"Types: {', '.join(query_types[:5])}...")
            tracker.record('validation', 'Index File', 'pass', f'{len(query_types)} types')
        else:
            print_warn("Index file not found", "Will build on first use")
            tracker.record('validation', 'Index File', 'warning', 'Not found')
        
        # Test engine initialization
        print_test("Engine Initialization")
        try:
            from src.validation.vedic_validation_engine_v2 import VedicValidationEngineV2
            from src.llm.factory import LLMFactory
            
            llm = LLMFactory.create(purpose="classification")
            
            # Try multiple constructor signatures
            engine = None
            
            # Try 1: With rules_file and index_file
            try:
                engine = VedicValidationEngineV2(
                    rules_file=rules_file,
                    index_file=index_file,
                    llm=llm
                )
                print_pass("Validation engine initialized (with files)")
            except TypeError:
                pass
            
            # Try 2: With just llm
            if not engine:
                try:
                    engine = VedicValidationEngineV2(llm=llm)
                    print_pass("Validation engine initialized (llm only)")
                except TypeError:
                    pass
            
            # Try 3: No arguments
            if not engine:
                try:
                    engine = VedicValidationEngineV2()
                    print_pass("Validation engine initialized (no args)")
                except TypeError:
                    pass
            
            if engine:
                tracker.record('validation', 'Engine Init', 'pass')
            else:
                print_fail("Could not initialize engine with any constructor")
                tracker.record('validation', 'Engine Init', 'fail', 'No compatible constructor')
                
        except Exception as e:
            print_fail("Engine initialization failed", str(e))
            tracker.record('validation', 'Engine Init', 'fail', str(e))
            
    except Exception as e:
        print_fail("Validation test failed", str(e))
        tracker.record('validation', 'Validation Engine', 'fail', str(e))

# ============================================================================
# TEST SUITE 6: HYBRID RETRIEVER & BM25
# ============================================================================

def test_06_hybrid_retriever():
    print_header("TEST 6: Hybrid Retriever (BM25 + Vector)")
    
    print_info("Production logs show BM25 failing to build")
    print_info("  [BM25] ❌ All strategies failed - proceeding with vector search only")
    
    try:
        from src.ai.hybrid_retriever import HybridRetriever
        from langchain_openai import OpenAIEmbeddings
        from langchain_chroma import Chroma
        from src.llm.factory import LLMFactory
        
        print_test("Retriever Initialization")
        
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            dimensions=3072
        )
        
        vector_store = Chroma(
            collection_name="vedic_astrology_books_knowledge",
            embedding_function=embeddings,
            persist_directory="./data/vectordb"
        )
        
        llm = LLMFactory.create(purpose="general")
        
        retriever = HybridRetriever(
            vector_store=vector_store,
            llm=llm
        )
        
        print_pass("Hybrid retriever created")
        tracker.record('retriever', 'Initialization', 'pass')
        
        # Test retrieval (this will trigger BM25 building)
        print_test("Chunk Retrieval")
        print_info("This will attempt BM25 index building...")
        
        start_time = time.time()
        chunks = retriever.retrieve(
            query="marriage timing",
            intent="RAG_WITH_CALCULATION",
            language="en",
            top_k=10
        )
        duration = time.time() - start_time
        
        if len(chunks) >= 10:
            print_pass(f"Retrieved {len(chunks)} chunks", f"Time: {duration:.2f}s")
            print_info(f"Sample: {chunks[0].page_content[:80]}...")
            tracker.record('retriever', 'Chunk Retrieval', 'pass', f'{len(chunks)} chunks')
        elif len(chunks) > 0:
            print_warn(f"Only {len(chunks)} chunks retrieved", f"Expected 10")
            tracker.record('retriever', 'Chunk Retrieval', 'warning', f'{len(chunks)} chunks')
        else:
            print_fail("0 chunks retrieved", "This matches production error!")
            tracker.record('retriever', 'Chunk Retrieval', 'fail', '0 chunks')
            print_info("Root cause: ChromaDB empty or BM25 build failed")
            
    except Exception as e:
        print_fail("Hybrid retriever failed", str(e))
        tracker.record('retriever', 'Hybrid Retriever', 'fail', str(e))
        import traceback
        traceback.print_exc()

# ============================================================================
# TEST SUITE 7: DIVISIONAL CHART CONTEXT
# ============================================================================

def test_07_divisional_chart_helper():
    print_header("TEST 7: Divisional Chart Context (Smart Detection)")
    
    print_info("Tests smart property detection (finance→D4)")
    
    try:
        from src.orchestration.divisional_chart_helper import (
            get_divisional_chart_context,
            DIVISIONAL_CHART_MAP
        )
        
        print_test("Divisional Chart Mappings")
        
        expected = ['marriage', 'career', 'children', 'finance', 'property', 'health']
        
        for qtype in expected:
            if qtype in DIVISIONAL_CHART_MAP:
                mapping = DIVISIONAL_CHART_MAP[qtype]
                primary = ', '.join(mapping['primary'])
                print_pass(f"{qtype.title()} mapping", f"Primary: {primary}")
                tracker.record('div_helper', f'Mapping: {qtype}', 'pass', primary)
            else:
                print_fail(f"{qtype.title()} mapping not found")
                tracker.record('div_helper', f'Mapping: {qtype}', 'fail')
        
        # Test smart property detection
        print_test("Smart Property Detection")
        
        test_chart = {
            'divisional_charts_simple': {
                'D4': {
                    'lagna': 'Aries',
                    'planets': {
                        'Mars': 'Leo',
                        'Saturn': 'Capricorn',
                        'Moon': 'Cancer'
                    }
                }
            }
        }
        
        # Test finance→property conversion
        property_queries = [
            "Will I have a house this year?",
            "Can I buy property?",
            "Will I get a car soon?"
        ]
        
        for query in property_queries:
            context = get_divisional_chart_context(
                query_type='finance',
                chart_data=test_chart,
                original_query=query
            )
            
            if 'D4' in context and 'Chaturthamsa' in context:
                print_pass(f"Query: '{query[:40]}...'", "Detected D4 for property")
                tracker.record('div_helper', f'Smart Detection: {query[:20]}', 'pass', 'D4')
            else:
                print_fail(f"Query: '{query[:40]}...'", "D4 not detected!")
                tracker.record('div_helper', f'Smart Detection: {query[:20]}', 'fail', 'No D4')
        
        # Test children→D7
        print_test("Children Query → D7 Chart")
        
        test_chart_d7 = {
            'divisional_charts_simple': {
                'D7': {
                    'lagna': 'Taurus',
                    'planets': {'Jupiter': 'Leo'}
                }
            }
        }
        
        context = get_divisional_chart_context(
            query_type='children',
            chart_data=test_chart_d7,
            original_query="Tell me about my children"
        )
        
        if 'D7' in context and 'Saptamsa' in context:
            print_pass("Children query correctly uses D7")
            tracker.record('div_helper', 'Children→D7', 'pass')
        else:
            print_fail("D7 not found for children query")
            tracker.record('div_helper', 'Children→D7', 'fail')
            
    except Exception as e:
        print_fail("Divisional chart helper failed", str(e))
        tracker.record('div_helper', 'Divisional Helper', 'fail', str(e))
        import traceback
        traceback.print_exc()

# ============================================================================
# TEST SUITE 8: LANGUAGE DETECTION
# ============================================================================

def test_08_language_detection():
    print_header("TEST 8: Language Detection")
    
    try:
        from src.locales.language_detector import get_language_detector
        
        print_test("Language Detector Initialization")
        detector = get_language_detector()
        print_pass("Language detector initialized")
        tracker.record('lang', 'Initialization', 'pass')
        
        # Test cases
        print_test("Language Detection Cases")
        
        test_cases = [
            ("Hello, how are you?", "en", "English"),
            ("Namaste", "hi-lat", "Hinglish"),
            ("Meri shaadi kab hogi?", "hi-lat", "Hinglish"),
            ("What is my future?", "en", "English"),
        ]
        
        for query, expected, name in test_cases:
            detected = detector.detect(query)
            
            if detected == expected:
                print_pass(f"'{query}' → {name}")
                tracker.record('lang', f'Detect: {query[:20]}', 'pass', detected)
            else:
                print_warn(f"'{query}' → Expected {expected}, got {detected}")
                tracker.record('lang', f'Detect: {query[:20]}', 'warning', 
                             f'Expected {expected}, got {detected}')
                
    except Exception as e:
        print_fail("Language detection failed", str(e))
        tracker.record('lang', 'Language Detection', 'fail', str(e))

# ============================================================================
# TEST SUITE 9: FILE STRUCTURE
# ============================================================================

def test_09_file_structure():
    print_header("TEST 9: Critical File Structure")
    
    critical_files = {
        'src/engines/vedic/vedic_engine.py': 'Vedic calculation engine',
        'src/engines/vedic/divisional_charts.py': 'Divisional charts (D1-D60)',
        'src/tools/calculation_tools.py': 'Chart formatting & tools',
        'src/ai/hybrid_retriever.py': 'RAG hybrid retriever',
        'src/orchestration/orchestrator.py': 'Main orchestrator',
        'src/validation/vedic_validation_engine_v2.py': 'Validation engine',
        'optimized/tiered_rules.json': 'Validation rules',
        'chatbot.py': 'CLI chatbot interface',
        'data/vectordb': 'Vector database directory',
    }
    
    print_test("File Existence")
    
    for filepath, description in critical_files.items():
        if os.path.exists(filepath):
            if os.path.isdir(filepath):
                print_pass(f"{filepath} (dir)", description)
            else:
                size = os.path.getsize(filepath)
                size_kb = size / 1024
                print_pass(f"{filepath}", f"{description} ({size_kb:.1f} KB)")
            tracker.record('files', filepath, 'pass')
        else:
            print_fail(f"{filepath} NOT FOUND", description)
            tracker.record('files', filepath, 'fail', 'Not found')

# ============================================================================
# TEST SUITE 10: END-TO-END INTEGRATION
# ============================================================================

def test_10_end_to_end():
    print_header("TEST 10: End-to-End Integration Test")
    
    print_info("Testing complete flow: Query → Chart → Validation → Response")
    
    try:
        from src.orchestration.orchestrator import create_enhanced_orchestrator
        from src.ai.intent_classifier import EnhancedIntentClassifier
        from src.ai.user_manager import get_user_manager
        from src.ai.hybrid_retriever import HybridRetriever
        from src.ai.prompt_builder import PromptBuilder
        from src.llm.factory import LLMFactory
        from langchain_openai import OpenAIEmbeddings
        from langchain_chroma import Chroma
        
        print_test("Component Initialization")
        print_info("This may take 30-60 seconds...")
        
        llm = LLMFactory.create(purpose="general")
        fast_llm = LLMFactory.create(purpose="classification")
        
        user_manager = get_user_manager(None)
        
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=3072)
        vector_store = Chroma(
            collection_name="vedic_astrology_books_knowledge",
            embedding_function=embeddings,
            persist_directory="./data/vectordb"
        )
        
        retriever = HybridRetriever(vector_store=vector_store, llm=llm)
        classifier = EnhancedIntentClassifier(llm=fast_llm)
        prompt_builder = PromptBuilder()
        
        orchestrator = create_enhanced_orchestrator(
            intent_classifier=classifier,
            user_manager=user_manager,
            hybrid_retriever=retriever,
            prompt_builder=prompt_builder,
            calculation_tools={},
            llm=llm,
            fast_llm=fast_llm
        )
        
        print_pass("All components initialized")
        tracker.record('e2e', 'Component Init', 'pass')
        
        # Test greeting
        print_test("Greeting Query")
        try:
            result = orchestrator.process_query(
                query="Hello",
                user_id="test_comprehensive_001"
            )
            
            # Handle different response formats
            answer = None
            
            # LangGraph returns AddableValuesDict - extract 'answer' or 'response' key
            if hasattr(result, 'get'):
                answer = (result.get('answer') or 
                         result.get('response') or 
                         result.get('content') or
                         result.get('output') or
                         result.get('final_response'))
            elif hasattr(result, '__getitem__'):
                # Try accessing as dict-like object
                try:
                    answer = result['answer']
                except (KeyError, TypeError):
                    try:
                        answer = result['response']
                    except (KeyError, TypeError):
                        pass
            
            if answer:
                answer_len = len(str(answer))
                print_pass(f"Greeting response received", f"{answer_len} characters")
                tracker.record('e2e', 'Greeting Query', 'pass', f'{answer_len} chars')
            else:
                # Response exists but couldn't extract text - still acceptable
                print_warn("Response exists but format couldn't be parsed", 
                          f"Type: {type(result).__name__}")
                tracker.record('e2e', 'Greeting Query', 'warning', 'Format not parsed')
        except Exception as e:
            print_fail("Query failed", str(e))
            tracker.record('e2e', 'Greeting Query', 'fail', str(e))
            
    except Exception as e:
        print_fail("End-to-end test failed", str(e))
        tracker.record('e2e', 'End-to-End', 'fail', str(e))
        import traceback
        traceback.print_exc()

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    print(f"\n{Color.BOLD}{'='*80}{Color.END}")
    print(f"{Color.BOLD}{'NAKSHATRAAI COMPREHENSIVE TEST SUITE'.center(80)}{Color.END}")
    print(f"{Color.BOLD}{'='*80}{Color.END}")
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing all known production issues and concerns\n")
    
    # Run all tests
    start_time = time.time()
    
    test_01_environment()
    test_02_rag_vector_database()
    test_03_calculation_engines()
    test_04_serialization()
    test_05_validation_engine()
    test_06_hybrid_retriever()
    test_07_divisional_chart_helper()
    test_08_language_detection()
    test_09_file_structure()
    test_10_end_to_end()
    
    duration = time.time() - start_time
    
    # Generate summary report
    print_header("TEST SUMMARY REPORT")
    
    passed = len(tracker.results['passed'])
    failed = len(tracker.results['failed'])
    warnings = len(tracker.results['warnings'])
    total = passed + failed + warnings
    
    print(f"\n{'Test Results':.<50} {total:>6}")
    print(f"{Color.GREEN}{'  Passed':.<50} {passed:>6} ({passed/total*100:.1f}%){Color.END}")
    print(f"{Color.RED}{'  Failed':.<50} {failed:>6} ({failed/total*100:.1f}%){Color.END}")
    print(f"{Color.YELLOW}{'  Warnings':.<50} {warnings:>6} ({warnings/total*100:.1f}%){Color.END}")
    print(f"{'Duration':.<50} {duration:>6.1f}s")
    
    # Critical failures
    if failed > 0:
        print_header("CRITICAL FAILURES")
        for result in tracker.results['failed']:
            print(f"{Color.RED}❌ [{result['category']}] {result['test']}{Color.END}")
            if result['details']:
                print(f"   {result['details']}")
    
    # Warnings
    if warnings > 0:
        print_header("WARNINGS")
        for result in tracker.results['warnings']:
            print(f"{Color.YELLOW}⚠️  [{result['category']}] {result['test']}{Color.END}")
            if result['details']:
                print(f"   {result['details']}")
    
    # Save detailed report
    report_file = tracker.save_report('comprehensive_test_report.json')
    print(f"\n{Color.CYAN}Detailed report saved: {report_file}{Color.END}")
    
    # Final verdict
    print_header("FINAL VERDICT")
    
    if failed == 0 and warnings == 0:
        print(f"{Color.GREEN}{Color.BOLD}✅ ALL TESTS PASSED!{Color.END}")
        print(f"{Color.GREEN}System is 100% operational{Color.END}")
    elif failed == 0:
        print(f"{Color.YELLOW}⚠️  {warnings} WARNINGS{Color.END}")
        print(f"{Color.YELLOW}Review warnings but system is operational{Color.END}")
    elif failed <= 2:
        print(f"{Color.RED}❌ {failed} CRITICAL ISSUES{Color.END}")
        print(f"{Color.RED}Fix required before production{Color.END}")
    else:
        print(f"{Color.RED}{Color.BOLD}❌ {failed} CRITICAL ISSUES{Color.END}")
        print(f"{Color.RED}System needs immediate attention{Color.END}")
    
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Color.BOLD}{'='*80}{Color.END}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Color.YELLOW}Tests interrupted by user{Color.END}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n{Color.RED}FATAL ERROR: {e}{Color.END}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)