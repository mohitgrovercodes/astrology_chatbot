# src/utils/cost_report.py
# src\utils\cost_report.py
"""
Cost Report CLI Tool.

Generate cost reports and query cost data from the command line.

Usage:
    python -m src.utils.cost_report --today
    python -m src.utils.cost_report --model gpt-4o-mini
    python -m src.utils.cost_report --date-range 2026-01-20 2026-01-24
    python -m src.utils.cost_report --export costs.csv
"""

import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .cost_logger import get_cost_logger, APICallLog, CostSummary


def format_currency(amount: float) -> str:
    """Format currency value."""
    return f"${amount:.6f}"


def format_number(num: int) -> str:
    """Format number with comma separators."""
    return f"{num:,}"


def print_summary_table(summary: CostSummary):
    """Print cost summary as a formatted table."""
    print("\n" + "=" * 80)
    print("COST SUMMARY")
    print("=" * 80)
    print(f"Period: {summary.start_date} to {summary.end_date}")
    print(f"Total API Calls: {format_number(summary.total_calls)}")
    print(f"Total Tokens: {format_number(summary.total_tokens)}")
    print(f"Total Cost: {format_currency(summary.total_cost)}")
    
    if summary.breakdown_by_model:
        print("\n" + "-" * 80)
        print("BREAKDOWN BY MODEL")
        print("-" * 80)
        print(f"{'Model':<30} {'Calls':>10} {'Tokens':>15} {'Cost':>15}")
        print("-" * 80)
        
        for model, stats in sorted(summary.breakdown_by_model.items()):
            print(
                f"{model:<30} "
                f"{stats['calls']:>10} "
                f"{format_number(stats['tokens']):>15} "
                f"{format_currency(stats['cost']):>15}"
            )
    
    if summary.breakdown_by_operation:
        print("\n" + "-" * 80)
        print("BREAKDOWN BY OPERATION")
        print("-" * 80)
        print(f"{'Operation':<30} {'Calls':>10} {'Tokens':>15} {'Cost':>15}")
        print("-" * 80)
        
        for operation, stats in sorted(summary.breakdown_by_operation.items()):
            print(
                f"{operation:<30} "
                f"{stats['calls']:>10} "
                f"{format_number(stats['tokens']):>15} "
                f"{format_currency(stats['cost']):>15}"
            )
    
    print("=" * 80 + "\n")


def print_calls_table(calls: list[APICallLog], limit: int = 50):
    """Print recent API calls as a formatted table."""
    print("\n" + "=" * 120)
    print("RECENT API CALLS")
    print("=" * 120)
    print(
        f"{'Timestamp':<20} "
        f"{'Model':<25} "
        f"{'Operation':<20} "
        f"{'In Tokens':>10} "
        f"{'Out Tokens':>10} "
        f"{'Cost':>12}"
    )
    print("-" * 120)
    
    for call in calls[:limit]:
        timestamp = call.timestamp.split('T')[1][:8]  # Just time portion
        print(
            f"{timestamp:<20} "
            f"{call.model_name:<25} "
            f"{call.operation:<20} "
            f"{format_number(call.input_tokens):>10} "
            f"{format_number(call.output_tokens):>10} "
            f"{format_currency(call.total_cost):>12}"
        )
    
    print("=" * 120 + "\n")


def export_to_csv(calls: list[APICallLog], output_file: str):
    """Export API calls to CSV file."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'Timestamp', 'Model', 'Model Type', 'Operation',
            'Input Tokens', 'Output Tokens', 'Total Tokens',
            'Input Cost', 'Output Cost', 'Total Cost'
        ])
        
        # Data rows
        for call in calls:
            writer.writerow([
                call.timestamp,
                call.model_name,
                call.model_type,
                call.operation,
                call.input_tokens,
                call.output_tokens,
                call.total_tokens,
                call.input_cost,
                call.output_cost,
                call.total_cost,
            ])
    
    print(f"[DONE] Exported {len(calls)} calls to {output_file}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cost Report Tool - Query and export LLM/Embedding API costs"
    )
    
    # Query filters
    parser.add_argument(
        '--today',
        action='store_true',
        help="Show costs for today only"
    )
    parser.add_argument(
        '--yesterday',
        action='store_true',
        help="Show costs for yesterday only"
    )
    parser.add_argument(
        '--week',
        action='store_true',
        help="Show costs for the past 7 days"
    )
    parser.add_argument(
        '--month',
        action='store_true',
        help="Show costs for the past 30 days"
    )
    parser.add_argument(
        '--date-range',
        nargs=2,
        metavar=('START', 'END'),
        help="Date range (YYYY-MM-DD format)"
    )
    parser.add_argument(
        '--model',
        type=str,
        help="Filter by model name"
    )
    parser.add_argument(
        '--operation',
        type=str,
        help="Filter by operation type"
    )
    
    # Output options
    parser.add_argument(
        '--recent',
        type=int,
        metavar='N',
        default=0,
        help="Show N most recent API calls"
    )
    parser.add_argument(
        '--export',
        type=str,
        metavar='FILE',
        help="Export detailed calls to CSV file"
    )
    parser.add_argument(
        '--db',
        type=str,
        default='./logs/cost_tracker.db',
        help="Path to cost tracker database (default: ./logs/cost_tracker.db)"
    )
    
    args = parser.parse_args()
    
    # Get cost logger
    try:
        cost_logger = get_cost_logger(db_path=args.db)
    except Exception as e:
        print(f"[ERROR] Failed to load cost database: {e}")
        sys.exit(1)
    
    # Determine date range
    start_date = None
    end_date = None
    
    if args.today:
        start_date = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
        end_date = datetime.now().isoformat()
    elif args.yesterday:
        yesterday = datetime.now() - timedelta(days=1)
        start_date = yesterday.replace(hour=0, minute=0, second=0).isoformat()
        end_date = yesterday.replace(hour=23, minute=59, second=59).isoformat()
    elif args.week:
        start_date = (datetime.now() - timedelta(days=7)).isoformat()
        end_date = datetime.now().isoformat()
    elif args.month:
        start_date = (datetime.now() - timedelta(days=30)).isoformat()
        end_date = datetime.now().isoformat()
    elif args.date_range:
        try:
            start_date = datetime.fromisoformat(args.date_range[0]).isoformat()
            end_date = datetime.fromisoformat(args.date_range[1]).isoformat()
        except ValueError:
            print("[ERROR] Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
    
    # Get and display summary
    summary = cost_logger.get_summary(start_date, end_date)
    
    # Apply additional filters for display
    if args.model or args.operation:
        print(f"\nFiltering by: ", end="")
        if args.model:
            print(f"model={args.model} ", end="")
        if args.operation:
            print(f"operation={args.operation}")
        print()
        
        # Get filtered cost
        filtered_cost = cost_logger.get_total_cost(
            start_date=start_date,
            end_date=end_date,
            model_name=args.model,
            operation=args.operation,
        )
        print(f"Filtered Total Cost: {format_currency(filtered_cost)}")
    
    print_summary_table(summary)
    
    # Show recent calls if requested
    if args.recent > 0:
        recent_calls = cost_logger.get_recent_calls(limit=args.recent)
        print_calls_table(recent_calls, limit=args.recent)
    
    # Export to CSV if requested
    if args.export:
        all_calls = cost_logger.get_recent_calls(limit=10000)  # Get many for export
        export_to_csv(all_calls, args.export)


if __name__ == "__main__":
    main()
