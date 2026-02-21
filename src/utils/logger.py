# src/utils/logger.py
# src\utils\logger.py
"""
Logging utility for Astrology AI Chatbot.

This module provides a centralized logging configuration that:
- Uses settings from config loader
- Supports both console and file logging
- Provides colored console output for better readability
- Offers convenience functions for common logging patterns
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


# ============================================
# Color Codes for Console Output
# ============================================

class LogColors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Levels
    DEBUG = "\033[36m"      # Cyan
    INFO = "\033[32m"       # Green
    WARNING = "\033[33m"    # Yellow
    ERROR = "\033[31m"      # Red
    CRITICAL = "\033[35m"   # Magenta


# ============================================
# Custom Formatter with Colors
# ============================================

class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to console output."""
    
    LEVEL_COLORS = {
        logging.DEBUG: LogColors.DEBUG,
        logging.INFO: LogColors.INFO,
        logging.WARNING: LogColors.WARNING,
        logging.ERROR: LogColors.ERROR,
        logging.CRITICAL: LogColors.CRITICAL,
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        # Add color to level name
        levelname = record.levelname
        if record.levelno in self.LEVEL_COLORS:
            colored_levelname = (
                f"{self.LEVEL_COLORS[record.levelno]}"
                f"{levelname}"
                f"{LogColors.RESET}"
            )
            record.levelname = colored_levelname
        
        # Format the message
        formatted = super().format(record)
        
        # Reset levelname for next use
        record.levelname = levelname
        
        return formatted


# ============================================
# Logger Setup Functions
# ============================================

def setup_logger(
    name: str = "astro_chatbot",
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    enable_file_logging: Optional[bool] = None,
    log_file_path: Optional[str] = None,
) -> logging.Logger:
    """
    Set up a logger with console and optional file output.
    
    Args:
        name: Logger name (typically module name or app name)
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                  If None, loads from config
        log_format: Log message format string
                   If None, loads from config
        enable_file_logging: Whether to log to file
                           If None, loads from config
        log_file_path: Path to log file
                      If None, loads from config
    
    Returns:
        Configured logger instance
    
    Example:
        >>> logger = setup_logger("my_module")
        >>> logger.info("This is an info message")
        >>> logger.error("This is an error")
    """
    # Get or create logger
    logger = logging.getLogger(name)
    
    # Prevent duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Load config if parameters not provided
    from src.utils.config import get_config
    config = get_config()
    
    if log_level is None:
        log_level = config.logging.level
    if log_format is None:
        log_format = config.logging.format
    if enable_file_logging is None:
        enable_file_logging = config.logging.file_logging
    if log_file_path is None:
        log_file_path = config.logging.log_file
    
    # Set log level
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Create console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_formatter = ColoredFormatter(log_format)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Create file handler if enabled
    if enable_file_logging:
        log_file = Path(log_file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        # File logging without colors
        file_formatter = logging.Formatter(log_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance. Creates it if it doesn't exist.
    
    This is the recommended way to get loggers throughout the application.
    
    Args:
        name: Logger name (typically __name__ of the module)
    
    Returns:
        Logger instance
    
    Example:
        >>> from src.utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Module initialized")
    """
    logger = logging.getLogger(name)
    
    # If logger has no handlers, set it up
    if not logger.handlers:
        logger = setup_logger(name)
    
    return logger


# ============================================
# Convenience Logging Functions
# ============================================

def log_config_summary() -> None:
    """
    Log a summary of the current configuration.
    
    Useful for debugging and startup diagnostics.
    """
    from src.utils.config import get_config
    
    logger = get_logger("config")
    config = get_config()
    
    logger.info("=" * 60)
    logger.info("CONFIGURATION SUMMARY")
    logger.info("=" * 60)
    
    logger.info(f"LLM Provider: {config.llm.default_provider}")
    logger.info(f"LLM Model: {config.llm.default_model}")
    logger.info(f"Temperature: {config.llm.temperature}")
    
    logger.info(f"Embedding Model: {config.embeddings.model}")
    logger.info(f"Embedding Dimensions: {config.embeddings.dimensions}")
    
    logger.info(f"RAG Top-K: {config.rag.top_k}")
    logger.info(f"RAG Collection: {config.rag.collection_name}")
    
    logger.info(f"ChromaDB Path: {config.env.chroma_persist_dir}")
    
    available_providers = config.get_available_providers()
    logger.info(f"Available Providers: {', '.join(available_providers)}")
    
    logger.info("=" * 60)


def log_llm_call(
    provider: str,
    model: str,
    prompt_length: int,
    response_length: int,
    duration_ms: float,
    logger: Optional[logging.Logger] = None
) -> None:
    """
    Log an LLM API call with key metrics.
    
    Args:
        provider: LLM provider name
        model: Model name
        prompt_length: Length of prompt in characters
        response_length: Length of response in characters
        duration_ms: Call duration in milliseconds
        logger: Logger instance (creates one if None)
    """
    if logger is None:
        logger = get_logger("llm")
    
    logger.debug(
        f"LLM Call | Provider: {provider} | Model: {model} | "
        f"Prompt: {prompt_length} chars | Response: {response_length} chars | "
        f"Duration: {duration_ms:.2f}ms"
    )


def log_rag_retrieval(
    query: str,
    num_results: int,
    avg_score: float,
    duration_ms: float,
    logger: Optional[logging.Logger] = None
) -> None:
    """
    Log a RAG retrieval operation.
    
    Args:
        query: Search query
        num_results: Number of documents retrieved
        avg_score: Average relevance score
        duration_ms: Retrieval duration in milliseconds
        logger: Logger instance (creates one if None)
    """
    if logger is None:
        logger = get_logger("rag")
    
    logger.debug(
        f"RAG Retrieval | Query: '{query[:50]}...' | "
        f"Results: {num_results} | Avg Score: {avg_score:.3f} | "
        f"Duration: {duration_ms:.2f}ms"
    )


def log_api_request(
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
    logger: Optional[logging.Logger] = None
) -> None:
    """
    Log an API request.
    
    Args:
        endpoint: API endpoint path
        method: HTTP method
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        logger: Logger instance (creates one if None)
    """
    if logger is None:
        logger = get_logger("api")
    
    level = logging.INFO if status_code < 400 else logging.ERROR
    
    logger.log(
        level,
        f"API Request | {method} {endpoint} | "
        f"Status: {status_code} | Duration: {duration_ms:.2f}ms"
    )


def log_error_with_context(
    error: Exception,
    context: str,
    logger: Optional[logging.Logger] = None
) -> None:
    """
    Log an error with additional context.
    
    Args:
        error: Exception that occurred
        context: Additional context about what was being done
        logger: Logger instance (creates one if None)
    """
    if logger is None:
        logger = get_logger("error")
    
    logger.error(
        f"Error in {context}: {type(error).__name__}: {str(error)}",
        exc_info=True
    )


# ============================================
# Main Logger Instance
# ============================================

# Create main application logger on import
main_logger = setup_logger("astro_chatbot")


# ============================================
# Testing
# ============================================

if __name__ == "__main__":
    """
    Test logging functionality.
    
    Run: python -m src.utils.logger
    """
    print("=" * 60)
    print("LOGGER TEST")
    print("=" * 60)
    print()
    
    # Test basic logging
    test_logger = get_logger("test")
    
    test_logger.debug("This is a DEBUG message")
    test_logger.info("This is an INFO message")
    test_logger.warning("This is a WARNING message")
    test_logger.error("This is an ERROR message")
    test_logger.critical("This is a CRITICAL message")
    
    print()
    
    # Test config summary
    try:
        log_config_summary()
    except Exception as e:
        test_logger.error(f"Could not log config summary: {e}")
    
    print()
    
    # Test convenience functions
    log_llm_call(
        provider="openai",
        model="gpt-4o-mini",
        prompt_length=150,
        response_length=500,
        duration_ms=1234.56
    )
    
    log_rag_retrieval(
        query="What is Jupiter in 7th house?",
        num_results=5,
        avg_score=0.87,
        duration_ms=45.23
    )
    
    log_api_request(
        endpoint="/chat",
        method="POST",
        status_code=200,
        duration_ms=1567.89
    )
    
    # Test error logging
    try:
        raise ValueError("This is a test error")
    except ValueError as e:
        log_error_with_context(e, "testing error logging")
    
    print()
    print("=" * 60)
    print("[DONE] Logger test complete!")
    print("=" * 60)