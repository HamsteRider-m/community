"""Nowledge Mem integration for GenericAgent.

This module is intentionally GenericAgent-specific:
- patches GenericAgent's system prompt builder to prepend Nowledge working memory
- adds nmem search/distill/save guidance to the prompt
- can be installed from a wrapper without modifying GenericAgent core files

Uses nmem HTTP API directly (no CLI dependency).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Import NmemClient from session_save module
try:
    from src.session_save import NmemClient
except ImportError:
    # Fallback for different import paths
    try:
        from session_save import NmemClient
    except ImportError:
        # If running from package root
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from session_save import NmemClient

_INSTALLED = False
_NMEM_CLIENT: Optional[NmemClient] = None

DEFAULT_TIMEOUT = float(os.environ.get("GENERICAGENT_NMEM_TIMEOUT", "4"))
MAX_WORKING_MEMORY_CHARS = int(os.environ.get("GENERICAGENT_NMEM_MAX_CHARS", "6000"))


def _get_nmem_client() -> Optional[NmemClient]:
    """Get or create NmemClient instance."""
    global _NMEM_CLIENT
    if _NMEM_CLIENT is None:
        try:
            _NMEM_CLIENT = NmemClient()
        except Exception:
            return None
    return _NMEM_CLIENT


def _compact_json_text(text: str, max_chars: int) -> str:
    text = text.strip()
    if not text:
        return ""
    try:
        data: Any = json.loads(text)
        if isinstance(data, dict):
            for key in ("content", "memory", "working_memory", "text", "markdown", "data"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    break
            else:
                text = json.dumps(data, ensure_ascii=False, indent=2)
        elif isinstance(data, list):
            text = json.dumps(data[:8], ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        pass
    return text[:max_chars]


def read_working_memory(max_chars: int = MAX_WORKING_MEMORY_CHARS) -> str:
    """Read working memory using nmem API.
    
    Returns:
        Working memory content as string, or empty string if unavailable.
    """
    client = _get_nmem_client()
    if not client:
        return ""
    
    try:
        # Use API instead of CLI
        data = client.read_working_memory()
        if data and data.get("exists"):
            content = data.get("content", "")
            if content:
                return _compact_json_text(content, max_chars)
    except Exception:
        # Silently fail - working memory is optional
        pass
    
    return ""


def install(module=None) -> bool:
    """Patch GenericAgent to inject Nowledge working memory and guidance.
    
    Args:
        module: Optional module parameter (for compatibility with wrapper)
    
    Returns:
        True if successfully installed, False otherwise.
    """
    global _INSTALLED
    if _INSTALLED:
        return True

    try:
        if module is None:
            import agentmain as target_module
        else:
            target_module = module
        original_get_system_prompt = target_module.get_system_prompt
    except (ImportError, AttributeError):
        return False

    # Patch the module-level function.

    def patched_get_system_prompt():
        """Patched version that injects working memory and nmem guidance."""
        # Call original function
        prompt = original_get_system_prompt()
        
        # Read working memory using API
        wm = read_working_memory()
        
        if wm:
            prompt += f"\n\n### [WORKING MEMORY]\n{wm}\n"
        
        # Add nmem guidance
        prompt += """

[Memory] (../memory)
Facts(L2): ../memory/global_mem.txt | CodeRoot: ../ | SOPs(L3): ../memory/*.md or *.py | META-SOP(L0): ../memory/memory_management_sop.md
L1 Insight is a minimal index; sync L1 when L2/L3 changes; keep index minimal. Read META-SOP(L0) before writing any memory.

You can use nmem CLI or MCP tools (if available) to:
- Search memories: `nmem search "query"` or `memory_search` tool
- Save insights: `nmem add "insight" -t "tag"` or `memory_add` tool
- Save this session: `nmem t save --from genericagent` or `save-thread` skill

Working memory is automatically loaded at session start.
"""
        return prompt

    # Apply the patch to the module-level function
    target_module.get_system_prompt = patched_get_system_prompt
    _INSTALLED = True
    return True


def save_insight(summary: str, project: str | None = None) -> bool:
    """Save an insight to nmem using API.
    
    Args:
        summary: The insight text to save
        project: Optional project name for tagging
        
    Returns:
        True if successfully saved, False otherwise.
    """
    client = _get_nmem_client()
    if not client:
        return False
    
    try:
        # Use memories API instead of CLI
        tags = ["GenericAgent handoff", "genericagent", "learning"]
        if project:
            tags.append(Path(project).name)
        
        # Note: This would require implementing memory_add in NmemClient
        # For now, we'll keep this as a placeholder
        # TODO: Implement memory_add API in NmemClient
        return False
    except Exception:
        return False
