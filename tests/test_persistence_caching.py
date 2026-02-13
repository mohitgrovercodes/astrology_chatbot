# tests\test_persistence_caching.py
import sys
from pathlib import Path
from datetime import datetime
import json
from dotenv import load_dotenv
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.engines.vedic.vedic_engine import VedicEngine, VedicChart
from src.rag.memory_retriever import MemoryRetriever
from src.db.sqlite_client import SQLiteClient

def test_chart_serialization():
    print("\n--- Test 1: VedicChart Serialization/Deserialization ---")
    engine = VedicEngine()
    
    # Generate original chart
    original_chart = engine.generate_chart(
        birth_date=datetime(1990, 3, 15, 14, 30),
        latitude=26.9124,
        longitude=75.7873
    )
    
    # Serialize to JSON
    chart_dict = original_chart.to_dict()
    chart_json = json.dumps(chart_dict)
    print(f"[OK] Serialized chart to {len(chart_json)} bytes")
    
    # Deserialize back
    deserialized_dict = json.loads(chart_json)
    reconstructed_chart = VedicChart.from_dict(deserialized_dict)
    print("[OK] Reconstructed chart from JSON")
    
    # Compare key results
    assert original_chart.rashi_name == reconstructed_chart.rashi_name
    assert original_chart.lagna.rashi_name == reconstructed_chart.lagna.rashi_name
    assert original_chart.moon_nakshatra == reconstructed_chart.moon_nakshatra
    
    # Deep check planetary position
    orig_sun = original_chart.positions[original_chart.positions.keys().__iter__().__next__()].longitude # get first
    for k, v in original_chart.positions.items():
        assert v.longitude == reconstructed_chart.positions[k].longitude
        
    print(f"[SUCCESS] Integrity check passed! Moon Sign: {reconstructed_chart.rashi_name}")

def test_memory_retriever():
    print("\n--- Test 2: MemoryRetriever (ChromaDB) ---")
    retriever = MemoryRetriever(collection_name="test_memories")
    
    user_id = "test_user_999"
    content = "The user mentioned they have a strong interest in career growth and recently started a new job in February 2026."
    
    # Clear old test data if any (simplified)
    # retriever.vector_store.delete(where={"user_id": user_id}) 
    
    # Add memory
    retriever.add_memory(user_id=user_id, content=content, role="turn")
    
    # Retrieve relevant memory
    query = "What did we talk about regarding my job?"
    results = retriever.retrieve_memories(user_id, query, k=1)
    
    assert len(results) > 0
    assert "February 2026" in results[0]['content']
    print(f"[SUCCESS] Retrieved match: {results[0]['content'][:50]}...")

def test_sqlite_cache_integration():
    print("\n--- Test 3: SQLite Cache Storage ---")
    client = SQLiteClient()
    user_id = "user001" # Existing test user
    
    # Update chart in DB
    dummy_json = json.dumps({"test": "data", "status": "cached"})
    client.update_user_chart(user_id, dummy_json)
    
    # Check if column exists and contains data
    conn = client.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT birth_chart_cache FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert "cached" in row[0]
    print(f"[SUCCESS] SQLite column 'birth_chart_cache' verified and writable.")

if __name__ == "__main__":
    try:
        test_chart_serialization()
        test_memory_retriever()
        test_sqlite_cache_integration()
        print("\n" + "="*40)
        print("ALL PERSISTENCE TESTS PASSED!")
        print("="*40)
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
