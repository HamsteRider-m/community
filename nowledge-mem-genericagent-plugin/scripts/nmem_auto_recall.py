#!/usr/bin/env python3
"""Auto-recall hook for GenericAgent × nmem.

Automatically injects relevant memories before each agent response.
Designed to be lightweight and non-blocking.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path


# Configuration
MAX_RECALL_MEMORIES = 3
RECALL_TIMEOUT = 2.0  # seconds
MIN_RELEVANCE_SCORE = 0.3


def get_relevant_memories(query, space=None, limit=MAX_RECALL_MEMORIES):
    """
    Search for relevant memories based on query.
    Returns list of memory snippets or empty list on failure.
    """
    try:
        cmd = ["nmem", "-j", "m", "search", query, "-n", str(limit)]
        if space:
            cmd.extend(["--space", space])
        
        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=RECALL_TIMEOUT
        )
        
        if result.returncode != 0:
            return []
        
        data = json.loads(result.stdout)
        memories = []
        
        for mem in data.get("results", [])[:limit]:
            memories.append({
                "id": mem.get("id"),
                "content": mem.get("content", "")[:200],  # Truncate to 200 chars
                "source": mem.get("source"),
                "created_at": mem.get("created_at")
            })
        
        return memories
    
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return []


def format_recall_context(memories):
    """Format memories as context injection."""
    if not memories:
        return ""
    
    lines = ["[Auto-recalled from nmem]"]
    for i, mem in enumerate(memories, 1):
        source = mem.get("source", "unknown")
        content = mem.get("content", "").strip()
        lines.append(f"{i}. [{source}] {content}")
    
    lines.append("[End of auto-recall]\n")
    return "\n".join(lines)


def should_recall(user_input):
    """
    Decide if auto-recall should be triggered.
    Skip for very short queries or system commands.
    """
    if not user_input or len(user_input.strip()) < 10:
        return False
    
    # Skip if it looks like a system command
    if user_input.strip().startswith(("/", "!", ".", "help", "exit", "quit")):
        return False
    
    return True


def auto_recall_hook(user_input, space=None):
    """
    Main hook function. Call this before processing user input.
    Returns context string to prepend to the input.
    """
    if not should_recall(user_input):
        return ""
    
    # Get space from env if not provided
    if space is None:
        space = os.environ.get("NMEM_SPACE")
    
    # Extract key terms from user input (simple approach)
    # In production, use better query extraction
    query = user_input[:100]  # Use first 100 chars as query
    
    memories = get_relevant_memories(query, space=space)
    return format_recall_context(memories)


def install_in_agent(agent_class):
    """
    Install auto-recall hook into an agent class.
    Wraps the agent's input processing method.
    """
    if hasattr(agent_class, "_nmem_auto_recall_installed"):
        return False
    
    original_process = getattr(agent_class, "process_input", None)
    if not original_process:
        return False
    
    def process_with_recall(self, user_input, *args, **kwargs):
        # Inject recalled context
        recall_context = auto_recall_hook(user_input)
        if recall_context:
            user_input = recall_context + "\n" + user_input
        
        return original_process(self, user_input, *args, **kwargs)
    
    agent_class.process_input = process_with_recall
    agent_class._nmem_auto_recall_installed = True
    return True


# CLI interface for testing
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test auto-recall functionality")
    parser.add_argument("query", help="Query to test")
    parser.add_argument("--space", help="Space to search in")
    parser.add_argument("-n", "--limit", type=int, default=3, help="Max memories")
    
    args = parser.parse_args()
    
    memories = get_relevant_memories(args.query, space=args.space, limit=args.limit)
    context = format_recall_context(memories)
    
    result = {
        "protocol": "nmem-auto-recall-v1/test",
        "query": args.query,
        "memories_found": len(memories),
        "context": context,
        "memories": memories
    }
    
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
