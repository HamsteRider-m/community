#!/usr/bin/env python3
"""
Session Save for GenericAgent - nmem integration

Monitors model_responses log files and automatically saves completed sessions
to nmem using the HTTP API (bypassing CLI limitations).

Based on openclaw's capture.js implementation.
"""

import ast

import json
import os
import re
import sys
import time
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class NmemClient:
    """Minimal nmem HTTP API client for thread operations."""
    
    def __init__(self, api_url: str = "http://127.0.0.1:14242", api_key: Optional[str] = None):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        
    def _request(self, method: str, path: str, body: Optional[Dict] = None, timeout: int = 30) -> Dict:
        """Make HTTP request to nmem API."""
        url = f"{self.api_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        data = json.dumps(body).encode("utf-8") if body else None
        
        try:
            req = Request(url, data=data, headers=headers, method=method)
            with urlopen(req, timeout=timeout) as response:
                response_text = response.read().decode("utf-8")
                return json.loads(response_text) if response_text else {}
        except HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_data = json.loads(error_body)
                detail = error_data.get("detail") or error_data.get("message") or error_body
            except:
                detail = error_body or f"HTTP {e.code}"
            raise Exception(f"nmem API error: {detail}")
        except URLError as e:
            raise Exception(f"nmem API connection error: {e.reason}")
    
    def create_thread(self, thread_id: Optional[str], title: str, messages: List[Dict], 
                     source: str = "genericagent") -> str:
        """Create a new thread in nmem."""
        if not title or not title.strip():
            raise ValueError("createThread requires a non-empty title")
        if not messages or len(messages) == 0:
            raise ValueError("createThread requires at least one message")
        
        body = {
            "title": title.strip(),
            "source": source,
            "messages": messages
        }
        
        if thread_id:
            body["thread_id"] = thread_id
        
        data = self._request("POST", "/threads", body)
        # API returns {"thread": {...}, "messages": [...]}
        # Extract thread_id from the thread object
        if "thread" in data and "thread_id" in data["thread"]:
            return data["thread"]["thread_id"]
        # Fallback to input thread_id if response structure is unexpected
        return thread_id if thread_id else "created"
    
    def append_thread(self, thread_id: str, messages: List[Dict], 
                     deduplicate: bool = True, idempotency_key: Optional[str] = None) -> Dict:
        """Append messages to an existing thread."""
        if not thread_id or not thread_id.strip():
            raise ValueError("appendThread requires threadId")
        if not messages or len(messages) == 0:
            return {"messages_added": 0, "total_messages": 0}
        
        body = {
            "messages": messages,
            "deduplicate": deduplicate
        }
        
        if idempotency_key:
            body["idempotency_key"] = idempotency_key
        
        # URL encode the thread_id for safety
        from urllib.parse import quote
        encoded_id = quote(thread_id, safe="")
        
        data = self._request("POST", f"/threads/{encoded_id}/append", body)
        return {
            "messages_added": data.get("messages_added", 0),
            "total_messages": data.get("total_messages", 0)
        }
    
    def get_thread_message_count(self, thread_id: str) -> Optional[int]:
        """Get the message count for a thread (returns None if not found)."""
        if not thread_id or not thread_id.strip():
            raise ValueError("getThreadMessageCount requires threadId")
        
        try:
            from urllib.parse import quote
            encoded_id = quote(thread_id, safe="")
            data = self._request("GET", f"/threads/{encoded_id}?limit=1", timeout=15)
            return data.get("message_count") or data.get("total_messages") or 0
        except Exception as e:
            if "not found" in str(e).lower() or "404" in str(e):
                return None
            raise
    
    def read_working_memory(self, space_id: Optional[str] = None) -> Optional[Dict]:
        """Read working memory from nmem.
        
        Returns:
            Dict with keys: exists (bool), content (str), date (str), parsed (dict)
            Returns None if working memory doesn't exist or on error
        """
        try:
            path = "/agent/working-memory"
            if space_id:
                path += f"?space_id={space_id}"
            
            data = self._request("GET", path, timeout=15)
            
            # API returns: {"exists": bool, "content": str, "date": str, "parsed": {...}}
            if data.get("exists"):
                return data
            return None
        except Exception as e:
            # Silently fail - working memory is optional
            return None


class SessionParser:
    """Parse GenericAgent model_responses log files."""
    
    @staticmethod
    def parse_log_file(file_path) -> Optional[Dict]:
        """Parse a model_responses log file and extract session data.
        
        GenericAgent logs are in format:
        === Prompt === YYYY-MM-DD HH:MM:SS
        {JSON content}
        
        === Response === YYYY-MM-DD HH:MM:SS
        [JSON array or dict]
        
        Args:
            file_path: Path to log file (str or Path object)
        """
        try:
            # Convert to Path if string
            if isinstance(file_path, str):
                file_path = Path(file_path)
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            if not content.strip():
                return None
            
            # Extract session metadata from filename
            # Format: model_responses_XXXXXX.txt
            match = re.search(r"model_responses_(\d+)\.txt$", file_path.name)
            session_id = match.group(1) if match else file_path.stem
            
            messages = []
            
            # Split by === Prompt === and === Response ===
            # Use optional \n at start to handle file beginning
            sections = re.split(r"(?:^|\n)=== (Prompt|Response) === [^\n]+\n", content, flags=re.MULTILINE)
            
            # Validate we have at least one complete Prompt-Response pair
            # sections[0] is preamble, then alternating type/content pairs
            # Minimum: preamble + "Prompt" + content + "Response" + content = 5 elements
            if len(sections) < 5:
                # File is too small or incomplete (need at least 1 complete exchange)
                return None
            
            # sections[0] is empty or preamble, then alternating type/content pairs
            for i in range(1, len(sections), 2):
                if i + 1 >= len(sections):
                    break
                
                section_type = sections[i]  # "Prompt" or "Response"
                section_content = sections[i + 1].strip()
                
                if not section_content:
                    continue
                
                try:
                    if section_type == "Prompt":
                        # Prompt is standard JSON
                        data = json.loads(section_content)
                        # Extract user message from prompt
                        text = SessionParser._extract_text_from_prompt(data)
                        if text:
                            messages.append({
                                "role": "user",
                                "content": text
                            })
                    
                    elif section_type == "Response":
                        # Response is Python list literal (not JSON)
                        # Use ast.literal_eval to safely parse Python syntax
                        data = ast.literal_eval(section_content)
                        # Extract assistant message from response
                        text = SessionParser._extract_text_from_response(data)
                        if text:
                            messages.append({
                                "role": "assistant",
                                "content": text
                            })
                
                except (json.JSONDecodeError, ValueError, SyntaxError):
                    # Skip malformed content
                    continue
            
            if not messages:
                return None
            
            # Generate title from first user message
            first_user_msg = next((m for m in messages if m["role"] == "user"), None)
            if first_user_msg:
                title = first_user_msg["content"][:100].strip()
                if len(first_user_msg["content"]) > 100:
                    title += "..."
            else:
                title = f"GenericAgent Session {session_id}"
            
            return {
                "session_id": session_id,
                "thread_id": f"ga-{session_id}",
                "title": title,
                "messages": messages,
                "file_path": str(file_path),
                "modified_time": file_path.stat().st_mtime
            }
        
        except Exception as e:
            print(f"Error parsing {file_path}: {e}", file=sys.stderr)
            return None
    
    @staticmethod
    def _extract_text_from_prompt(data: Any) -> Optional[str]:
        """Extract text content from a prompt JSON structure."""
        if isinstance(data, dict):
            # Check for content array
            content = data.get("content")
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text = item.get("text", "")
                            if text:
                                texts.append(text)
                        elif item.get("type") == "tool_result":
                            # Skip tool results in user messages
                            continue
                if texts:
                    return "\n".join(texts)
            
            # Check for direct text field
            if "text" in data:
                return data["text"]
        
        return None
    
    @staticmethod
    def _extract_text_from_response(data: Any) -> Optional[str]:
        """Extract text content from a response JSON structure."""
        if isinstance(data, list):
            # Response is an array of content blocks
            texts = []
            for item in data:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        if text:
                            texts.append(text)
            if texts:
                return "\n".join(texts)
        
        elif isinstance(data, dict):
            # Response is a single object
            if data.get("type") == "text":
                return data.get("text", "")
            
            # Check for content field
            content = data.get("content")
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                return SessionParser._extract_text_from_response(content)
        
        return None
    
    @staticmethod
    def build_thread_id(session_id: str) -> str:
        """Build a stable thread ID for a session."""
        return f"ga-{session_id}"


class SessionSaver:
    """Main session save orchestrator."""
    
    def __init__(self, log_dir: Path, client: NmemClient, state_file: Optional[Path] = None):
        self.log_dir = log_dir
        self.client = client
        self.state_file = state_file or (log_dir / ".session_save_state.json")
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load saved state (tracks which sessions have been saved)."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"saved_sessions": {}}
    
    def _save_state(self):
        """Save state to disk."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save state: {e}", file=sys.stderr)
    
    def _is_session_saved(self, session_id: str, message_count: int) -> bool:
        """Check if a session has already been saved."""
        saved = self.state["saved_sessions"].get(session_id)
        if not saved:
            return False
        return saved.get("message_count", 0) >= message_count
    
    def _mark_session_saved(self, session_id: str, message_count: int):
        """Mark a session as saved."""
        self.state["saved_sessions"][session_id] = {
            "message_count": message_count,
            "saved_at": datetime.now().isoformat()
        }
        self._save_state()
    
    def save_session(self, session_data: Dict, force: bool = False) -> bool:
        """Save a session to nmem."""
        session_id = session_data["session_id"]
        thread_id = session_data["thread_id"]
        messages = session_data["messages"]
        
        # Check if already saved
        if not force and self._is_session_saved(session_id, len(messages)):
            return False
        
        try:
            # Check if thread exists
            existing_count = self.client.get_thread_message_count(thread_id)
            
            if existing_count is None:
                # Thread doesn't exist, create it
                created_id = self.client.create_thread(
                    thread_id=thread_id,
                    title=session_data["title"],
                    messages=messages,
                    source="genericagent"
                )
                print(f"✓ Created thread {created_id} with {len(messages)} messages")
                self._mark_session_saved(session_id, len(messages))
                return True
            
            elif existing_count < len(messages):
                # Thread exists but has fewer messages, append the delta
                new_messages = messages[existing_count:]
                result = self.client.append_thread(
                    thread_id=thread_id,
                    messages=new_messages,
                    deduplicate=True
                )
                added = result["messages_added"]
                if added > 0:
                    print(f"✓ Appended {added} messages to thread {thread_id}")
                    self._mark_session_saved(session_id, len(messages))
                    return True
            
            # Already up to date
            return False
        
        except Exception as e:
            print(f"✗ Failed to save session {session_id}: {e}", file=sys.stderr)
            return False
    
    def scan_and_save(self, pattern: str = "model_responses_*.txt") -> int:
        """Scan log directory and save all sessions."""
        saved_count = 0
        
        for log_file in sorted(self.log_dir.glob(pattern)):
            session_data = SessionParser.parse_log_file(log_file)
            if session_data and self.save_session(session_data):
                saved_count += 1
        
        return saved_count


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Save GenericAgent sessions to nmem")
    parser.add_argument("--log-dir", type=Path, 
                       default=Path.home() / "Projects/GenericAgent/temp/model_responses",
                       help="Directory containing model_responses logs")
    parser.add_argument("--api-url", default="http://127.0.0.1:14242",
                       help="nmem API URL")
    parser.add_argument("--api-key", help="nmem API key (optional)")
    parser.add_argument("--watch", action="store_true",
                       help="Watch for new sessions and save continuously")
    parser.add_argument("--interval", type=int, default=30,
                       help="Watch interval in seconds (default: 30)")
    
    args = parser.parse_args()
    
    if not args.log_dir.exists():
        print(f"Error: Log directory not found: {args.log_dir}", file=sys.stderr)
        sys.exit(1)
    
    client = NmemClient(api_url=args.api_url, api_key=args.api_key)
    saver = SessionSaver(log_dir=args.log_dir, client=client)
    
    if args.watch:
        print(f"Watching {args.log_dir} for new sessions (interval: {args.interval}s)")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                saved = saver.scan_and_save()
                if saved > 0:
                    print(f"Saved {saved} session(s)")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped")
    else:
        # One-time scan
        saved = saver.scan_and_save()
        print(f"Saved {saved} session(s)")


if __name__ == "__main__":
    main()
