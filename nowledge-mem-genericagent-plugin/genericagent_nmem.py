"""Nowledge Mem integration for GenericAgent.

This module is intentionally GenericAgent-specific:
- patches GenericAgent's system prompt builder to prepend Nowledge working memory
- adds nmem search/distill/save guidance to the prompt
- can be installed from a wrapper without modifying GenericAgent core files
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Iterable

_INSTALLED = False

DEFAULT_TIMEOUT = float(os.environ.get("GENERICAGENT_NMEM_TIMEOUT", "4"))
MAX_WORKING_MEMORY_CHARS = int(os.environ.get("GENERICAGENT_NMEM_MAX_CHARS", "6000"))


def _run_nmem(args: Iterable[str], timeout: float = DEFAULT_TIMEOUT) -> subprocess.CompletedProcess[str] | None:
    cmd = ["nmem", *args]
    try:
        return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


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


def read_working_memory() -> str:
    """Read Nowledge working memory, preferring the nmem JSON API."""
    attempts = (("--json", "wm", "read"), ("wm", "read"))
    for args in attempts:
        proc = _run_nmem(args)
        if proc and proc.returncode == 0:
            content = _compact_json_text(proc.stdout, MAX_WORKING_MEMORY_CHARS)
            if content:
                return content
    return ""


def get_nmem_status_text() -> str:
    proc = _run_nmem(("status",), timeout=8)
    if proc is None:
        return "nmem status unavailable: CLI not found, timed out, or failed to launch."
    output = (proc.stdout or proc.stderr or "").strip()
    if not output:
        output = f"nmem status exited {proc.returncode} with no output."
    return output[:2000]



def build_prompt_block() -> str:
    working = read_working_memory()
    nmem_status = get_nmem_status_text()
    integration_status = "working-memory-loaded" if working else "installed; working memory empty or unreadable"
    lines = [
        "",
        "[Nowledge Mem / nmem integration for GenericAgent]",
        f"Integration status: {integration_status}.",
        "nmem runtime status for the user:",
        nmem_status,
        "",
        "Behavior:",
        "- Treat this as a GenericAgent-specific nmem integration, not a Codex plugin.",
        "- Tell the user the visible nmem runtime status when they ask whether memory is available.",
        "- Prefer MCP tools for memory retrieval/writes when this GenericAgent runtime exposes Nowledge Mem MCP tools; otherwise use the nmem CLI.",
        "- If neither MCP tools nor the nmem CLI are available, state that the integration is installed but memory access is unavailable.",
        "",
        "CLI fallback commands:",
        "- Working memory: `nmem --json wm read`.",
        "- Durable memory search: `nmem --json m search \"query\" -n 5`.",
        "- Prior-session/thread search: `nmem --json t search \"query\" -n 5 --source genericagent`.",
        "- Durable save: `nmem m add \"content\" -t \"title\" -l genericagent --unit-type learning` only for durable, useful, user-approved memories.",
        "- Diagnostics: `nmem status`.",
        "",
        "Direct MCP configuration for hosts that support MCP:",
        "- Server name: `nowledge-mem`.",
        "- URL: `http://127.0.0.1:14242/mcp/`.",
        "- Type: `streamableHttp`.",
        "- Remote/custom configs can be generated with `nmem config mcp show --host <host>` after `nmem config client set url ...` and `nmem config client set api-key ...`.",
        "- Direct MCP clients do not automatically read `~/.nowledge-mem/config.json`; configure the host MCP settings explicitly.",
    ]
    if working:
        lines.extend(["", "[Nowledge Working Memory]", working])
    return "\n".join(lines).rstrip() + "\n"


def install(agentmain_module: Any | None = None) -> bool:
    """Patch an imported `agentmain` module so every task receives nmem context."""
    global _INSTALLED
    if _INSTALLED:
        return True
    if agentmain_module is None:
        try:
            import agentmain as agentmain_module  # type: ignore
        except Exception:
            return False

    original_get_system_prompt = getattr(agentmain_module, "get_system_prompt", None)
    if not callable(original_get_system_prompt):
        return False

    def get_system_prompt_with_nmem() -> str:
        prompt = original_get_system_prompt()
        return prompt + build_prompt_block()

    agentmain_module.get_system_prompt = get_system_prompt_with_nmem
    _INSTALLED = True
    return True


def export_handoff(summary: str, project: str | None = None) -> bool:
    """Save a concise GenericAgent handoff into Nowledge Mem."""
    args = ["m", "add", summary, "-t", "GenericAgent handoff", "-l", "genericagent", "--unit-type", "learning"]
    if project:
        args.extend(["-l", Path(project).name])
    proc = _run_nmem(args, timeout=15)
    return bool(proc and proc.returncode == 0)


def shell_quote(args: Iterable[str]) -> str:
    return " ".join(shlex.quote(a) for a in args)
