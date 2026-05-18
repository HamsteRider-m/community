#!/usr/bin/env python3
"""Entity tracking wrapper for GenericAgent × nmem.

Uses nmem graph expand/evolves + memory search for entity tracking.
"""
import argparse
import json
import subprocess
import sys


def run_nmem(args):
    """Run nmem CLI with JSON output."""
    cmd = ["nmem", "-j"] + args
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        print(f"Error: nmem command failed", file=sys.stderr)
        print(f"Command: {' '.join(cmd)}", file=sys.stderr)
        print(f"STDERR: {p.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.stdout)


def cmd_search(args):
    """Search for entity mentions across memories."""
    # Use memory search to find entity mentions
    nmem_args = ["m", "search", args.entity, "-n", str(args.limit)]
    if args.space:
        nmem_args.extend(["--space", args.space])
    
    data = run_nmem(nmem_args)
    
    result = {
        "protocol": "nmem-entity-v1/search",
        "entity": args.entity,
        "mentions": data.get("results", []),
        "total": data.get("total"),
        "rule": "These are memory snippets mentioning the entity. Use 'expand' to see relationships."
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_expand(args):
    """Expand graph neighborhood around a memory (shows related entities)."""
    nmem_args = ["g", "expand", args.memory_id]
    if args.depth:
        nmem_args.extend(["--depth", str(args.depth)])
    
    data = run_nmem(nmem_args)
    
    result = {
        "protocol": "nmem-entity-v1/expand",
        "memory_id": args.memory_id,
        "neighborhood": data,
        "rule": "Shows memories and entities connected to this memory."
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_evolves(args):
    """Show version chain for a memory (entity evolution over time)."""
    nmem_args = ["g", "evolves", args.memory_id]
    data = run_nmem(nmem_args)
    
    result = {
        "protocol": "nmem-entity-v1/evolves",
        "memory_id": args.memory_id,
        "versions": data,
        "rule": "Shows how this entity/memory evolved over time."
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="Entity tracking for GenericAgent × nmem",
        epilog="""Examples:
  # Search for entity mentions
  nmem_entity_tracker.py search "GenericAgent" -n 10
  
  # Search in specific space
  nmem_entity_tracker.py search "nmem" --space research -n 5
  
  # Expand graph around a memory
  nmem_entity_tracker.py expand mem-abc123 --depth 2
  
  # Show entity evolution
  nmem_entity_tracker.py evolves mem-abc123
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # search command
    p_search = subparsers.add_parser("search", help="Search for entity mentions")
    p_search.add_argument("entity", help="Entity name to search")
    p_search.add_argument("-n", "--limit", type=int, default=10, help="Max results")
    p_search.add_argument("--space", help="Search in specific space")
    p_search.set_defaults(func=cmd_search)
    
    # expand command
    p_expand = subparsers.add_parser("expand", help="Expand graph neighborhood")
    p_expand.add_argument("memory_id", help="Memory ID to expand from")
    p_expand.add_argument("--depth", type=int, help="Expansion depth")
    p_expand.set_defaults(func=cmd_expand)
    
    # evolves command
    p_evolves = subparsers.add_parser("evolves", help="Show entity evolution")
    p_evolves.add_argument("memory_id", help="Memory ID to trace")
    p_evolves.set_defaults(func=cmd_evolves)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
