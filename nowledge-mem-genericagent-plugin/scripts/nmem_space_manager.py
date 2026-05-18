#!/usr/bin/env python3
"""Space management wrapper for GenericAgent × nmem.

Provides convenient space operations for context-aware memory management.
"""
import argparse
import json
import os
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


def cmd_list(args):
    """List all spaces."""
    data = run_nmem(["spaces", "list"])
    
    result = {
        "protocol": "nmem-space-v1/list",
        "spaces": data.get("spaces", []),
        "current": os.environ.get("NMEM_SPACE", "default"),
        "rule": "Use 'switch' to change active space, or pass --space to individual commands."
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_show(args):
    """Show space details."""
    data = run_nmem(["spaces", "show", args.name])
    
    result = {
        "protocol": "nmem-space-v1/show",
        "space": data
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_create(args):
    """Create a new space."""
    nmem_args = ["spaces", "create", args.name]
    if args.icon:
        nmem_args.extend(["--icon", args.icon])
    if args.instructions:
        nmem_args.extend(["--instructions", args.instructions])
    
    data = run_nmem(nmem_args)
    
    result = {
        "protocol": "nmem-space-v1/create",
        "space": data,
        "message": f"Space '{args.name}' created successfully."
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_switch(args):
    """Switch to a different space (sets NMEM_SPACE env var)."""
    # Verify space exists
    spaces_data = run_nmem(["spaces", "list"])
    space_names = [s.get("name") for s in spaces_data.get("spaces", [])]
    
    if args.name not in space_names:
        print(f"Error: Space '{args.name}' does not exist.", file=sys.stderr)
        print(f"Available spaces: {', '.join(space_names)}", file=sys.stderr)
        sys.exit(1)
    
    # Output shell command to set env var
    result = {
        "protocol": "nmem-space-v1/switch",
        "space": args.name,
        "shell_command": f"export NMEM_SPACE='{args.name}'",
        "message": f"To switch to space '{args.name}', run:",
        "instructions": [
            f"export NMEM_SPACE='{args.name}'",
            "# Or add to your shell profile for persistence:",
            f"echo 'export NMEM_SPACE=\"{args.name}\"' >> ~/.zshrc  # or ~/.bashrc"
        ]
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_current(args):
    """Show current active space."""
    current = os.environ.get("NMEM_SPACE", "default")
    
    result = {
        "protocol": "nmem-space-v1/current",
        "space": current,
        "env_var": "NMEM_SPACE",
        "message": f"Current space: {current}"
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_update(args):
    """Update space configuration."""
    nmem_args = ["spaces", "update", args.name]
    if args.instructions:
        nmem_args.extend(["--instructions", args.instructions])
    if args.retrieval_mode:
        nmem_args.extend(["--retrieval-mode", args.retrieval_mode])
    if args.share_with:
        nmem_args.extend(["--share-with", args.share_with])
    
    data = run_nmem(nmem_args)
    
    result = {
        "protocol": "nmem-space-v1/update",
        "space": data,
        "message": f"Space '{args.name}' updated successfully."
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="Space management for GenericAgent × nmem",
        epilog="""Examples:
  # List all spaces
  nmem_space_manager.py list
  
  # Show current space
  nmem_space_manager.py current
  
  # Create a new space
  nmem_space_manager.py create "Research" --icon brain --instructions "Focus on research notes"
  
  # Switch to a space (outputs shell command)
  nmem_space_manager.py switch "Research"
  
  # Show space details
  nmem_space_manager.py show "Research"
  
  # Update space configuration
  nmem_space_manager.py update "Research" --instructions "Updated instructions"
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # list command
    p_list = subparsers.add_parser("list", help="List all spaces")
    p_list.set_defaults(func=cmd_list)
    
    # current command
    p_current = subparsers.add_parser("current", help="Show current active space")
    p_current.set_defaults(func=cmd_current)
    
    # show command
    p_show = subparsers.add_parser("show", help="Show space details")
    p_show.add_argument("name", help="Space name")
    p_show.set_defaults(func=cmd_show)
    
    # create command
    p_create = subparsers.add_parser("create", help="Create a new space")
    p_create.add_argument("name", help="Space name")
    p_create.add_argument("--icon", help="Space icon")
    p_create.add_argument("--instructions", help="Space instructions")
    p_create.set_defaults(func=cmd_create)
    
    # switch command
    p_switch = subparsers.add_parser("switch", help="Switch to a space")
    p_switch.add_argument("name", help="Space name")
    p_switch.set_defaults(func=cmd_switch)
    
    # update command
    p_update = subparsers.add_parser("update", help="Update space configuration")
    p_update.add_argument("name", help="Space name")
    p_update.add_argument("--instructions", help="Update instructions")
    p_update.add_argument("--retrieval-mode", choices=["shared", "isolated"], help="Retrieval mode")
    p_update.add_argument("--share-with", help="Share with space")
    p_update.set_defaults(func=cmd_update)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
