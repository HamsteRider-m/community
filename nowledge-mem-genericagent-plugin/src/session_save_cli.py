#!/usr/bin/env python3
"""
CLI tool to manually save a GenericAgent session to nmem.

Usage:
    python session_save_cli.py <log_file>
    python session_save_cli.py --latest
"""

import sys
import argparse
from pathlib import Path
from session_save import SessionParser, NmemClient


def find_latest_log(log_dir: Path) -> Path:
    """Find the most recently modified log file."""
    log_files = list(log_dir.glob("model_responses_*.txt"))
    if not log_files:
        raise FileNotFoundError(f"No log files found in {log_dir}")
    return max(log_files, key=lambda f: f.stat().st_mtime)


def main():
    parser = argparse.ArgumentParser(
        description="Save GenericAgent session to nmem"
    )
    parser.add_argument(
        "log_file",
        nargs="?",
        help="Path to model_responses_*.txt file"
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Process the most recently modified log file"
    )
    parser.add_argument(
        "--log-dir",
        default=str(Path.home() / "Projects/GenericAgent/temp/model_responses"),
        help="Directory containing log files (for --latest)"
    )
    
    args = parser.parse_args()
    
    # Determine which file to process
    if args.latest:
        log_dir = Path(args.log_dir)
        log_file = find_latest_log(log_dir)
        print(f"Processing latest log: {log_file.name}")
    elif args.log_file:
        log_file = Path(args.log_file)
    else:
        parser.print_help()
        sys.exit(1)
    
    if not log_file.exists():
        print(f"Error: File not found: {log_file}")
        sys.exit(1)
    
    # Parse and save
    print(f"Parsing {log_file.name}...")
    result = SessionParser.parse_log_file(log_file)
    
    if not result:
        print("Error: Failed to parse log file")
        sys.exit(1)
    
    print(f"  Session ID: {result['session_id']}")
    print(f"  Title: {result['title'][:60]}...")
    print(f"  Messages: {len(result['messages'])}")
    
    # Create thread in nmem
    client = NmemClient()
    try:
        thread_id = client.create_thread(
            thread_id=result["thread_id"],
            title=result["title"],
            messages=result["messages"],
            source="genericagent"
        )
        print(f"✓ Saved to nmem: {thread_id}")
    except Exception as e:
        if "already exists" in str(e):
            print(f"⚠ Thread {result['thread_id']} already exists in nmem")
        else:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
