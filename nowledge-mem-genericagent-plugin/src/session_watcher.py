#!/usr/bin/env python3
"""
GenericAgent Session Watcher for nmem.

Monitors model_responses directory for new/modified log files and automatically
saves completed sessions to nmem.
"""

import sys
import time
import logging
from pathlib import Path
from typing import Set, Dict, Optional
from datetime import datetime

from session_save import SessionParser, NmemClient


class SessionWatcher:
    """Watch GenericAgent log directory and auto-save sessions to nmem."""
    
    def __init__(
        self,
        log_dir: Path,
        check_interval: int = 10,
        min_file_age: int = 30,
    ):
        """
        Initialize the session watcher.
        
        Args:
            log_dir: Directory containing model_responses_*.txt files
            check_interval: Seconds between directory scans
            min_file_age: Minimum seconds since last modification before processing
        """
        self.log_dir = Path(log_dir)
        self.check_interval = check_interval
        self.min_file_age = min_file_age
        
        self.client = NmemClient()
        self.processed_files: Set[str] = set()
        self.file_states: Dict[str, float] = {}  # filename -> last_mtime
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
    
    def scan_directory(self) -> None:
        """Scan log directory for new or modified files."""
        if not self.log_dir.exists():
            self.logger.warning(f"Log directory does not exist: {self.log_dir}")
            return
        
        current_time = time.time()
        
        for log_file in self.log_dir.glob("model_responses_*.txt"):
            filename = log_file.name
            mtime = log_file.stat().st_mtime
            
            # Skip if already processed
            if filename in self.processed_files:
                continue
            
            # Check if file is stable (not being written to)
            if current_time - mtime < self.min_file_age:
                self.logger.debug(f"Skipping {filename} (too recent)")
                continue
            
            # Check if file has been modified since last scan
            last_mtime = self.file_states.get(filename)
            if last_mtime is not None and mtime == last_mtime:
                # File hasn't changed, process it
                self.process_file(log_file)
            else:
                # File is new or has changed, update state
                self.file_states[filename] = mtime
                self.logger.debug(f"Tracking {filename} (mtime: {mtime})")
    
    def process_file(self, log_file: Path) -> None:
        """Process a log file and save to nmem."""
        filename = log_file.name
        
        try:
            self.logger.info(f"Processing {filename}...")
            
            # Parse the log file
            session_data = SessionParser.parse_log_file(log_file)
            
            if not session_data:
                self.logger.warning(f"Failed to parse {filename}")
                self.processed_files.add(filename)
                return
            
            thread_id = session_data["thread_id"]
            
            # Check if thread already exists
            existing_count = self.client.get_thread_message_count(thread_id)
            
            if existing_count is not None:
                # Thread exists, check if we need to append
                new_message_count = len(session_data["messages"])
                
                if new_message_count > existing_count:
                    # Append new messages
                    messages_to_add = session_data["messages"][existing_count:]
                    result = self.client.append_thread(
                        thread_id=thread_id,
                        messages=messages_to_add,
                        deduplicate=True
                    )
                    self.logger.info(
                        f"✓ Appended {result['messages_added']} messages to {thread_id} "
                        f"(total: {result['total_messages']})"
                    )
                else:
                    self.logger.info(f"✓ Thread {thread_id} already up-to-date")
            else:
                # Thread doesn't exist, create it
                created_id = self.client.create_thread(
                    thread_id=thread_id,
                    title=session_data["title"],
                    messages=session_data["messages"],
                    source="genericagent"
                )
                self.logger.info(
                    f"✓ Created thread {created_id} with {len(session_data['messages'])} messages"
                )
            
            # Mark as processed
            self.processed_files.add(filename)
            
        except Exception as e:
            self.logger.error(f"Error processing {filename}: {e}", exc_info=True)
            # Don't mark as processed so we can retry later
    
    def run(self) -> None:
        """Run the watcher loop."""
        self.logger.info(f"Starting session watcher...")
        self.logger.info(f"  Log directory: {self.log_dir}")
        self.logger.info(f"  Check interval: {self.check_interval}s")
        self.logger.info(f"  Min file age: {self.min_file_age}s")
        self.logger.info(f"  nmem API: {self.client.api_url}")
        
        try:
            while True:
                self.scan_directory()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Watch GenericAgent logs and auto-save to nmem"
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path.home() / "Projects/GenericAgent/temp/model_responses",
        help="Directory containing model_responses_*.txt files"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Seconds between directory scans (default: 10)"
    )
    parser.add_argument(
        "--min-age",
        type=int,
        default=30,
        help="Minimum seconds since last modification before processing (default: 30)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    watcher = SessionWatcher(
        log_dir=args.log_dir,
        check_interval=args.interval,
        min_file_age=args.min_age
    )
    
    watcher.run()


if __name__ == "__main__":
    main()
