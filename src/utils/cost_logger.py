# src/utils/cost_logger.py
# src\utils\cost_logger.py
"""
Cost Logger for Astrology AI Chatbot.

Tracks all LLM and embedding API usage with accurate cost calculation.
Provides both detailed per-call logs and aggregate cost summaries.

Key Features:
- SQLite storage for efficient querying
- Accurate pricing for all supported models
- Both detailed and aggregate views
- CLI reporting tools
- Thread-safe logging
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from threading import Lock
from enum import Enum

from .logger import get_logger

logger = get_logger(__name__)


# ============================================
# Model Pricing Definitions
# ============================================

class ModelType(Enum):
    """Model type classification."""
    LLM = "llm"
    EMBEDDING = "embedding"
    VISION = "vision"


@dataclass
class ModelPricing:
    """Pricing information for a model."""
    model_name: str
    model_type: ModelType
    input_price_per_1k: float  # USD per 1K tokens
    output_price_per_1k: float  # USD per 1K tokens (0 for embeddings)
    context_window: int
    notes: str = ""


# Pricing as of January 2026
PRICING_TABLE = {
    # Gemini 2.5 Models (Pricing as of Jan 2026)
    "gemini-2.5-pro": ModelPricing(
        model_name="gemini-2.5-pro",
        model_type=ModelType.LLM,
        input_price_per_1k=0.00125,    
        output_price_per_1k=0.01000,   
        context_window=2_000_000,
        notes="Standard tier pricing"
    ),
    "gemini-2.5-flash": ModelPricing(
        model_name="gemini-2.5-flash",
        model_type=ModelType.LLM,
        input_price_per_1k=0.00030,   
        output_price_per_1k=0.00250,   
        context_window=1_000_000,
    ),
    "gemini-2.5-flash-lite": ModelPricing(
        model_name="gemini-2.5-flash-lite",
        model_type=ModelType.LLM,
        input_price_per_1k=0.00010, 
        output_price_per_1k=0.00040,
        context_window=1_000_000,
        notes="Flash-Lite Preview pricing"
    ),
    
    
    # OpenAI Models
    "gpt-4o-mini": ModelPricing(
        model_name="gpt-4o-mini",
        model_type=ModelType.LLM,
        input_price_per_1k=0.00015,
        output_price_per_1k=0.00060,
        context_window=128_000,
        notes="Standard pricing"
    ),
    "gpt-4o": ModelPricing(
        model_name="gpt-4o",
        model_type=ModelType.LLM,
        input_price_per_1k=0.00250,
        output_price_per_1k=0.01000,
        context_window=128_000,
    ),
    
    # OpenAI Embedding Models
    "text-embedding-3-large": ModelPricing(
        model_name="text-embedding-3-large",
        model_type=ModelType.EMBEDDING,
        input_price_per_1k=0.00013,
        output_price_per_1k=0.0,
        context_window=8191,
    ),
    "text-embedding-3-small": ModelPricing(
        model_name="text-embedding-3-small",
        model_type=ModelType.EMBEDDING,
        input_price_per_1k=0.00002,
        output_price_per_1k=0.0,
        context_window=8191,
    ),
}


# ============================================
# Data Models
# ============================================

@dataclass
class APICallLog:
    """Detailed log of a single API call."""
    timestamp: str
    model_name: str
    model_type: str
    operation: str  # 'llm_generation', 'vision_extraction', 'embedding', etc.
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    metadata: Dict[str, Any]  # Additional context (file, phase, etc.)
    call_id: Optional[str] = None  # Auto-generated


@dataclass
class CostSummary:
    """Aggregate cost summary for a time period or filter."""
    start_date: str
    end_date: str
    total_calls: int
    total_tokens: int
    total_cost: float
    breakdown_by_model: Dict[str, Dict[str, Any]]  # model -> {calls, tokens, cost}
    breakdown_by_operation: Dict[str, Dict[str, Any]]  # operation -> {calls, tokens, cost}


# ============================================
# Cost Logger
# ============================================

class CostLogger:
    """
    Thread-safe cost logger with SQLite backend.
    
    Features:
    - Log individual API calls with detailed metadata
    - Generate aggregate cost summaries
    - Query and filter cost data
    - Export reports in multiple formats
    """
    
    def __init__(
        self,
        db_path: str = "./logs/cost_tracker.db",
        enabled: bool = True,
    ):
        """
        Initialize cost logger.
        
        Args:
            db_path: Path to SQLite database
            enabled: Whether logging is enabled
        """
        self.db_path = Path(db_path)
        self.enabled = enabled
        self._lock = Lock()
        
        if self.enabled:
            # Create logs directory
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Initialize database
            self._init_database()
            
            logger.info(f"CostLogger initialized: {self.db_path}")
    
    def _init_database(self):
        """Initialize SQLite database with schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Detailed API call logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    input_cost REAL NOT NULL,
                    output_cost REAL NOT NULL,
                    total_cost REAL NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Aggregate daily summaries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    total_calls INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    total_cost REAL NOT NULL,
                    breakdown_by_model TEXT,
                    breakdown_by_operation TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON api_calls(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_model 
                ON api_calls(model_name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_operation 
                ON api_calls(operation)
            """)
            
            conn.commit()
    
    def calculate_cost(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Tuple[float, float, float]:
        """
        Calculate cost for an API call.
        
        Args:
            model_name: Name of the model
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Tuple of (input_cost, output_cost, total_cost) in USD
        """
        # Normalize model name (remove prefixes)
        normalized_name = model_name.replace("models/", "").replace("gpt-", "gpt-")
        
        # Get pricing info
        pricing = PRICING_TABLE.get(normalized_name)
        
        if not pricing:
            logger.warning(f"Unknown model '{model_name}', using fallback pricing of $0")
            return (0.0, 0.0, 0.0)
        
        # Calculate costs
        input_cost = (input_tokens / 1000.0) * pricing.input_price_per_1k
        output_cost = (output_tokens / 1000.0) * pricing.output_price_per_1k
        total_cost = input_cost + output_cost
        
        return (input_cost, output_cost, total_cost)
    
    def log_api_call(
        self,
        model_name: str,
        model_type: str,
        operation: str,
        input_tokens: int,
        output_tokens: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Log a single API call.
        
        Args:
            model_name: Name of the model used
            model_type: Type of model ('llm', 'embedding', 'vision')
            operation: Operation type (e.g., 'vision_extraction', 'embedding')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            metadata: Additional context information
            
        Returns:
            Database row ID if successful, None otherwise
        """
        if not self.enabled:
            return None
        
        try:
            # Calculate costs
            input_cost, output_cost, total_cost = self.calculate_cost(
                model_name, input_tokens, output_tokens
            )
            
            total_tokens = input_tokens + output_tokens
            timestamp = datetime.now().isoformat()
            
            # Create log entry
            log_entry = APICallLog(
                timestamp=timestamp,
                model_name=model_name,
                model_type=model_type,
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                input_cost=input_cost,
                output_cost=output_cost,
                total_cost=total_cost,
                metadata=metadata or {},
            )
            
            # Store in database
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO api_calls (
                            timestamp, model_name, model_type, operation,
                            input_tokens, output_tokens, total_tokens,
                            input_cost, output_cost, total_cost, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        log_entry.timestamp,
                        log_entry.model_name,
                        log_entry.model_type,
                        log_entry.operation,
                        log_entry.input_tokens,
                        log_entry.output_tokens,
                        log_entry.total_tokens,
                        log_entry.input_cost,
                        log_entry.output_cost,
                        log_entry.total_cost,
                        json.dumps(log_entry.metadata),
                    ))
                    row_id = cursor.lastrowid
                    conn.commit()
                
                # Update daily summary
                self._update_daily_summary(timestamp, log_entry)
            
            logger.debug(
                f"Logged {operation}: {model_name}, "
                f"{total_tokens} tokens, ${total_cost:.6f}"
            )
            
            return row_id
            
        except Exception as e:
            logger.error(f"Failed to log API call: {e}")
            return None
    
    def log_llm_call(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        operation: str = "llm_generation",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Log an LLM generation call.
        
        Args:
            model_name: LLM model name
            input_tokens: Input token count
            output_tokens: Output token count
            operation: Operation type (default: 'llm_generation')
            metadata: Additional context
            
        Returns:
            Database row ID if successful
        """
        return self.log_api_call(
            model_name=model_name,
            model_type=ModelType.LLM.value,
            operation=operation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata=metadata,
        )
    
    def log_vision_call(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Log a vision/multimodal LLM call.
        
        Args:
            model_name: Vision model name
            input_tokens: Input token count
            output_tokens: Output token count
            metadata: Additional context (e.g., page number, file name)
            
        Returns:
            Database row ID if successful
        """
        return self.log_api_call(
            model_name=model_name,
            model_type=ModelType.VISION.value,
            operation="vision_extraction",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata=metadata,
        )
    
    def log_embedding_call(
        self,
        model_name: str,
        tokens: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Log an embedding generation call.
        
        Args:
            model_name: Embedding model name
            tokens: Total token count
            metadata: Additional context (e.g., batch size, chunk IDs)
            
        Returns:
            Database row ID if successful
        """
        return self.log_api_call(
            model_name=model_name,
            model_type=ModelType.EMBEDDING.value,
            operation="embedding",
            input_tokens=tokens,
            output_tokens=0,
            metadata=metadata,
        )
    
    def _update_daily_summary(self, timestamp: str, log_entry: APICallLog):
        """Update daily summary with new API call."""
        date = timestamp.split('T')[0]  # Extract date (YYYY-MM-DD)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get existing summary for this date
            cursor.execute("""
                SELECT total_calls, total_tokens, total_cost,
                       breakdown_by_model, breakdown_by_operation
                FROM daily_summaries WHERE date = ?
            """, (date,))
            
            row = cursor.fetchone()
            
            if row:
                # Update existing summary
                total_calls, total_tokens, total_cost, model_breakdown, op_breakdown = row
                total_calls += 1
                total_tokens += log_entry.total_tokens
                total_cost += log_entry.total_cost
                
                # Parse JSON breakdowns
                model_breakdown = json.loads(model_breakdown) if model_breakdown else {}
                op_breakdown = json.loads(op_breakdown) if op_breakdown else {}
            else:
                # Create new summary
                total_calls = 1
                total_tokens = log_entry.total_tokens
                total_cost = log_entry.total_cost
                model_breakdown = {}
                op_breakdown = {}
            
            # Update breakdowns
            model_key = log_entry.model_name
            if model_key not in model_breakdown:
                model_breakdown[model_key] = {"calls": 0, "tokens": 0, "cost": 0.0}
            model_breakdown[model_key]["calls"] += 1
            model_breakdown[model_key]["tokens"] += log_entry.total_tokens
            model_breakdown[model_key]["cost"] += log_entry.total_cost
            
            op_key = log_entry.operation
            if op_key not in op_breakdown:
                op_breakdown[op_key] = {"calls": 0, "tokens": 0, "cost": 0.0}
            op_breakdown[op_key]["calls"] += 1
            op_breakdown[op_key]["tokens"] += log_entry.total_tokens
            op_breakdown[op_key]["cost"] += log_entry.total_cost
            
            # Upsert summary
            cursor.execute("""
                INSERT OR REPLACE INTO daily_summaries (
                    date, total_calls, total_tokens, total_cost,
                    breakdown_by_model, breakdown_by_operation, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                date,
                total_calls,
                total_tokens,
                total_cost,
                json.dumps(model_breakdown),
                json.dumps(op_breakdown),
                datetime.now().isoformat(),
            ))
            
            conn.commit()
    
    def get_total_cost(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        model_name: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> float:
        """
        Get total cost for filtered API calls.
        
        Args:
            start_date: Start date (ISO format, inclusive)
            end_date: End date (ISO format, inclusive)
            model_name: Filter by model name
            operation: Filter by operation type
            
        Returns:
            Total cost in USD
        """
        if not self.enabled:
            return 0.0
        
        query = "SELECT SUM(total_cost) FROM api_calls WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        if operation:
            query += " AND operation = ?"
            params.append(operation)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()[0]
        
        return result if result else 0.0
    
    def get_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> CostSummary:
        """
        Get aggregate cost summary for a date range.
        
        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            
        Returns:
            CostSummary object
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).isoformat()
        if not end_date:
            end_date = datetime.now().isoformat()
        
        query = """
            SELECT 
                COUNT(*) as total_calls,
                SUM(total_tokens) as total_tokens,
                SUM(total_cost) as total_cost,
                model_name,
                operation
            FROM api_calls
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY model_name, operation
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (start_date, end_date))
            rows = cursor.fetchall()
        
        total_calls = 0
        total_tokens = 0
        total_cost = 0.0
        breakdown_by_model = {}
        breakdown_by_operation = {}
        
        for row in rows:
            calls, tokens, cost, model, operation = row
            total_calls += calls
            total_tokens += tokens or 0
            total_cost += cost or 0.0
            
            # Model breakdown
            if model not in breakdown_by_model:
                breakdown_by_model[model] = {"calls": 0, "tokens": 0, "cost": 0.0}
            breakdown_by_model[model]["calls"] += calls
            breakdown_by_model[model]["tokens"] += tokens or 0
            breakdown_by_model[model]["cost"] += cost or 0.0
            
            # Operation breakdown
            if operation not in breakdown_by_operation:
                breakdown_by_operation[operation] = {"calls": 0, "tokens": 0, "cost": 0.0}
            breakdown_by_operation[operation]["calls"] += calls
            breakdown_by_operation[operation]["tokens"] += tokens or 0
            breakdown_by_operation[operation]["cost"] += cost or 0.0
        
        return CostSummary(
            start_date=start_date,
            end_date=end_date,
            total_calls=total_calls,
            total_tokens=total_tokens,
            total_cost=total_cost,
            breakdown_by_model=breakdown_by_model,
            breakdown_by_operation=breakdown_by_operation,
        )
    
    def get_recent_calls(self, limit: int = 50) -> List[APICallLog]:
        """
        Get most recent API calls.
        
        Args:
            limit: Maximum number of calls to return
            
        Returns:
            List of APICallLog objects
        """
        query = """
            SELECT timestamp, model_name, model_type, operation,
                   input_tokens, output_tokens, total_tokens,
                   input_cost, output_cost, total_cost, metadata
            FROM api_calls
            ORDER BY timestamp DESC
            LIMIT ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
        
        calls = []
        for row in rows:
            calls.append(APICallLog(
                timestamp=row[0],
                model_name=row[1],
                model_type=row[2],
                operation=row[3],
                input_tokens=row[4],
                output_tokens=row[5],
                total_tokens=row[6],
                input_cost=row[7],
                output_cost=row[8],
                total_cost=row[9],
                metadata=json.loads(row[10]) if row[10] else {},
            ))
        
        return calls


# ============================================
# Singleton Instance
# ============================================

_cost_logger_instance: Optional[CostLogger] = None


def get_cost_logger(
    db_path: str = "./logs/cost_tracker.db",
    enabled: bool = True,
    reload: bool = False,
) -> CostLogger:
    """
    Get the global cost logger instance (singleton).
    
    Args:
        db_path: Path to SQLite database
        enabled: Whether logging is enabled
        reload: Force reload of logger
        
    Returns:
        CostLogger instance
        
    Example:
        >>> from src.utils.cost_logger import get_cost_logger
        >>> logger = get_cost_logger()
        >>> logger.log_llm_call("gemini-2.5-flash", 1000, 500)
    """
    global _cost_logger_instance
    
    if _cost_logger_instance is None or reload:
        _cost_logger_instance = CostLogger(db_path=db_path, enabled=enabled)
    
    return _cost_logger_instance


# ============================================
# Testing
# ============================================

if __name__ == "__main__":
    """
    Test cost logger functionality.
    
    Run: python -m src.utils.cost_logger
    """
    print("=" * 70)
    print("COST LOGGER TEST")
    print("=" * 70)
    print()
    
    # Create test logger
    test_db = "./logs/test_cost_tracker.db"
    if Path(test_db).exists():
        Path(test_db).unlink()
    
    cost_logger = CostLogger(db_path=test_db)
    
    # Test LLM call logging
    print("Testing LLM call logging...")
    cost_logger.log_llm_call(
        model_name="gemini-2.5-flash",
        input_tokens=1500,
        output_tokens=800,
        metadata={"test": "llm_call"}
    )
    print("[DONE] LLM call logged")
    
    # Test embedding call logging
    print("\nTesting embedding call logging...")
    cost_logger.log_embedding_call(
        model_name="text-embedding-3-large",
        tokens=2048,
        metadata={"batch_size": 10}
    )
    print("[DONE] Embedding call logged")
    
    # Test vision call logging
    print("\nTesting vision call logging...")
    cost_logger.log_vision_call(
        model_name="gemini-2.5-flash",
        input_tokens=2000,
        output_tokens=1000,
        metadata={"page": 5, "file": "test.pdf"}
    )
    print("[DONE] Vision call logged")
    
    # Get summary
    print("\n" + "=" * 70)
    print("COST SUMMARY")
    print("=" * 70)
    
    summary = cost_logger.get_summary()
    print(f"Total Calls: {summary.total_calls}")
    print(f"Total Tokens: {summary.total_tokens:,}")
    print(f"Total Cost: ${summary.total_cost:.6f}")
    
    print("\nBreakdown by Model:")
    for model, stats in summary.breakdown_by_model.items():
        print(f"  {model}:")
        print(f"    Calls: {stats['calls']}")
        print(f"    Tokens: {stats['tokens']:,}")
        print(f"    Cost: ${stats['cost']:.6f}")
    
    print("\nBreakdown by Operation:")
    for operation, stats in summary.breakdown_by_operation.items():
        print(f"  {operation}:")
        print(f"    Calls: {stats['calls']}")
        print(f"    Tokens: {stats['tokens']:,}")
        print(f"    Cost: ${stats['cost']:.6f}")
    
    print("\n" + "=" * 70)
    print("[DONE] Cost Logger test complete!")
    print("=" * 70)
