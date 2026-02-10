"""
Multilingual RAG Performance Test

Tests current OpenAI embeddings vs Cohere multilingual embeddings
to determine if upgrade is worth the cost.

Test queries in:
- Hindi (native script)
- Tamil (native script)  
- Hinglish (romanized)
- Domain-specific terms (Sanskrit)

Measures:
- Retrieval accuracy (manual inspection)
- Semantic similarity scores
- Domain term matching
"""

import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import List, Dict, Any
import json
from dataclasses import dataclass

# Import RAG components
from src.rag.retriever import AstrologyRetriever


@dataclass
class TestQuery:
    """Test query with expected results."""
    language: str
    query: str
    query_en: str  # English translation for reference
    expected_topics: List[str]  # Topics that SHOULD be retrieved
    difficulty: str  # 'simple', 'domain', 'sanskrit'


# Test Dataset
TEST_QUERIES = [
    # Simple queries (universal concepts)
    TestQuery(
        language="hindi",
        query="मेरी राशि क्या है?",
        query_en="What is my zodiac sign?",
        expected_topics=["zodiac", "sign", "rashi", "birth chart"],
        difficulty="simple"
    ),
    TestQuery(
        language="tamil",
        query="என் சந்திர ராசி என்ன?",
        query_en="What is my moon sign?",
        expected_topics=["moon", "sign", "rashi", "chandra"],
        difficulty="simple"
    ),
    
    # Domain-specific queries
    TestQuery(
        language="hindi",
        query="शनि की साढ़ेसाती कब शुरू होती है?",
        query_en="When does Sade Sati start?",
        expected_topics=["saturn", "sade sati", "shani", "7.5 years", "transit"],
        difficulty="domain"
    ),
    TestQuery(
        language="hindi",
        query="महादशा और अंतर्दशा में क्या अंतर है?",
        query_en="What is the difference between Mahadasha and Antardasha?",
        expected_topics=["mahadasha", "antardasha", "dasha", "period", "vimshottari"],
        difficulty="domain"
    ),
    
    # Sanskrit/Romanized queries
    TestQuery(
        language="hinglish",
        query="Guru aur Shani ka yog kya hai?",
        query_en="What is Jupiter-Saturn conjunction?",
        expected_topics=["jupiter", "saturn", "conjunction", "yoga", "guru"],
        difficulty="sanskrit"
    ),
    TestQuery(
        language="hinglish",
        query="Lagna mein Mangal hone se kya hota hai?",
        query_en="What happens when Mars is in the ascendant?",
        expected_topics=["mars", "ascendant", "lagna", "mangal", "1st house"],
        difficulty="sanskrit"
    ),
    
    # Complex astrological concepts
    TestQuery(
        language="tamil",
        query="நவாம்ச கட்டத்தில் சுக்கிரன் என்ன பலன் தருவார்?",
        query_en="What results does Venus give in Navamsa chart?",
        expected_topics=["venus", "navamsa", "d9", "divisional chart", "shukra"],
        difficulty="domain"
    ),
]


class RAGTester:
    """Test RAG retrieval quality across languages."""
    
    def __init__(self, collection_name='astrology_default'):
        """Initialize with current retriever."""
        try:
            self.retriever = AstrologyRetriever(collection_name=collection_name)
            if self.retriever.collection:
                print(f"[OK] Loaded retriever with {self.retriever.collection.count()} chunks")
            else:
                print(f"[ERROR] Collection '{collection_name}' not found")
                self.retriever = None
        except Exception as e:
            print(f"[ERROR] Failed to load retriever: {e}")
            self.retriever = None
    
    def test_query(self, test: TestQuery, top_k: int = 5) -> Dict[str, Any]:
        """
        Test a single query and evaluate results.
        
        Returns:
            dict with results and quality metrics
        """
        if not self.retriever:
            return {"error": "Retriever not initialized"}
        
        print(f"\n{'='*70}")
        print(f"Language: {test.language.upper()}")
        print(f"Query: {test.query}")
        print(f"English: {test.query_en}")
        print(f"Difficulty: {test.difficulty}")
        print(f"{'='*70}")
        
        # Retrieve chunks
        try:
            chunks = self.retriever.retrieve(test.query, top_k=top_k)
        except Exception as e:
            print(f"[ERROR] Retrieval error: {e}")
            return {"error": str(e)}
        
        if not chunks:
            print("[ERROR] No chunks retrieved!")
            return {"chunks": [], "relevance_score": 0.0}
        
        # Evaluate results
        results = {
            "query": test.query,
            "query_en": test.query_en,
            "language": test.language,
            "difficulty": test.difficulty,
            "chunks": [],
            "avg_score": 0.0,
            "topic_coverage": 0.0,
            "manual_review_needed": []
        }
        
        print(f"\nRetrieved {len(chunks)} chunks:\n")
        
        total_score = 0.0
        topics_found = set()
        
        for i, chunk in enumerate(chunks, 1):
            # Extract info
            source = chunk.metadata.get('source_book', 'Unknown')
            chapter = chunk.metadata.get('chapter', '')
            snippet = chunk.display_text[:150] + "..." if len(chunk.display_text) > 150 else chunk.display_text
            score = chunk.score
            
            # Check topic coverage
            chunk_text_lower = chunk.text.lower()
            matched_topics = [
                topic for topic in test.expected_topics 
                if topic.lower() in chunk_text_lower
            ]
            topics_found.update(matched_topics)
            
            # Display
            print(f"[{i}] Score: {score:.3f} | Source: {source}")
            if chapter:
                print(f"    Chapter: {chapter}")
            print(f"    Topics: {matched_topics if matched_topics else 'None'}")
            print(f"    Text: {snippet}\n")
            
            # Save for analysis
            results["chunks"].append({
                "rank": i,
                "score": score,
                "source": source,
                "chapter": chapter,
                "snippet": snippet,
                "matched_topics": matched_topics
            })
            
            total_score += score
        
        # Calculate metrics
        results["avg_score"] = total_score / len(chunks) if chunks else 0.0
        results["topic_coverage"] = len(topics_found) / len(test.expected_topics) if test.expected_topics else 0.0
        
        # Summary
        print(f"{'='*70}")
        print(f"RESULTS SUMMARY:")
        print(f"  Average Similarity: {results['avg_score']:.3f}")
        print(f"  Topic Coverage: {results['topic_coverage']:.1%} ({len(topics_found)}/{len(test.expected_topics)})")
        print(f"  Topics Found: {sorted(topics_found)}")
        print(f"  Topics Missed: {sorted(set(test.expected_topics) - topics_found)}")
        
        # Quality assessment
        if results["avg_score"] > 0.7 and results["topic_coverage"] > 0.6:
            quality = "[GOOD]"
        elif results["avg_score"] > 0.5 and results["topic_coverage"] > 0.4:
            quality = "[OKAY]"
        else:
            quality = "[POOR]"
        
        print(f"  Quality: {quality}")
        print(f"{'='*70}")
        
        return results
    
    def run_full_test_suite(self) -> Dict[str, Any]:
        """Run all test queries and generate report."""
        print("\n" + "="*70)
        print("MULTILINGUAL RAG PERFORMANCE TEST")
        print("="*70)
        print(f"Testing {len(TEST_QUERIES)} queries across languages")
        print(f"Embedding Model: OpenAI text-embedding-3-large (current)")
        print("="*70)
        
        all_results = []
        
        for test in TEST_QUERIES:
            result = self.test_query(test)
            all_results.append(result)
        
        # Generate summary report
        report = self._generate_report(all_results)
        
        return report
    
    def _generate_report(self, results: List[Dict]) -> Dict[str, Any]:
        """Generate summary report from all test results."""
        print("\n" + "="*70)
        print("FINAL REPORT")
        print("="*70)
        
        # Group by difficulty
        by_difficulty = {'simple': [], 'domain': [], 'sanskrit': []}
        for r in results:
            if 'error' not in r:
                by_difficulty[r['difficulty']].append(r)
        
        # Calculate averages
        report = {
            "overall": {
                "avg_similarity": sum(r['avg_score'] for r in results if 'error' not in r) / len(results),
                "avg_coverage": sum(r['topic_coverage'] for r in results if 'error' not in r) / len(results),
            },
            "by_difficulty": {}
        }
        
        for difficulty, res_list in by_difficulty.items():
            if res_list:
                report["by_difficulty"][difficulty] = {
                    "count": len(res_list),
                    "avg_similarity": sum(r['avg_score'] for r in res_list) / len(res_list),
                    "avg_coverage": sum(r['topic_coverage'] for r in res_list) / len(res_list),
                }
        
        # Print report
        print(f"\nOVERALL PERFORMANCE:")
        print(f"  Average Similarity: {report['overall']['avg_similarity']:.3f}")
        print(f"  Average Topic Coverage: {report['overall']['avg_coverage']:.1%}")
        
        print(f"\nBY DIFFICULTY:")
        for difficulty, metrics in report["by_difficulty"].items():
            print(f"\n  {difficulty.upper()} ({metrics['count']} queries):")
            print(f"    Similarity: {metrics['avg_similarity']:.3f}")
            print(f"    Coverage: {metrics['avg_coverage']:.1%}")
        
        # Quality grades
        print(f"\nQUALITY ASSESSMENT:")
        overall_score = (report['overall']['avg_similarity'] + report['overall']['avg_coverage']) / 2
        
        if overall_score >= 0.75:
            grade = "A (Excellent)"
            recommendation = "Current embeddings working well!"
        elif overall_score >= 0.60:
            grade = "B (Good)"
            recommendation = "Current embeddings acceptable, upgrade optional"
        elif overall_score >= 0.45:
            grade = "C (Fair)"
            recommendation = "Consider upgrading for better quality"
        else:
            grade = "D (Poor)"
            recommendation = "STRONGLY recommend multilingual embeddings"
        
        print(f"  Overall Grade: {grade}")
        print(f"  Recommendation: {recommendation}")
        
        print("="*70)
        
        report["grade"] = grade
        report["recommendation"] = recommendation
        
        return report


def main():
    """Run the test suite."""
    tester = RAGTester()
    
    if not tester.retriever:
        print("ERROR: Could not initialize retriever. Check your vector database.")
        return
    
    # Run tests
    report = tester.run_full_test_suite()
    
    # Save report
    output_file = "multilingual_rag_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n[OK] Full report saved to: {output_file}")


if __name__ == "__main__":
    main()
