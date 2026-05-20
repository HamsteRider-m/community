"""GenericAgent central completion hook for nmem session save.

This module patches GenericAgent's central queue consumer method (`put_task`) so
all frontends that send completed user/assistant turns through that queue get a
single automatic session-save path. It avoids filesystem log watching as the
primary mechanism; watcher/backfill tools remain fallback only.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import weakref
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .session_save import NmemClient
except ImportError:  # pragma: no cover - direct script/import path fallback
    from session_save import NmemClient

MAX_USER_CHARS = int(os.environ.get("GENERICAGENT_NMEM_SESSION_MAX_USER_CHARS", "12000"))
MAX_ASSISTANT_CHARS = int(os.environ.get("GENERICAGENT_NMEM_SESSION_MAX_ASSISTANT_CHARS", "24000"))
SOURCE = os.environ.get("GENERICAGENT_NMEM_SESSION_SOURCE", "genericagent")

_ARCHIVES: "weakref.WeakKeyDictionary[Any, NmemSessionArchive]" = weakref.WeakKeyDictionary()


def _clip(value: Any, limit: int) -> str:
    text = "" if value is None else str(value)
    if limit > 0 and len(text) > limit:
        return text[:limit] + f"\n\n[truncated {len(text) - limit} chars]"
    return text


def _stable_thread_id(agent: Any) -> str:
    task_dir = getattr(agent, "task_dir", "") or ""
    session_id = getattr(agent, "session_id", "") or ""
    seed = session_id or task_dir or f"pid-{os.getpid()}-{id(agent)}"
    digest = hashlib.sha256(str(seed).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"ga-{digest}"


def _turn_idempotency_key(thread_id: str, user_text: str, assistant_text: str) -> str:
    digest = hashlib.sha256(
        json.dumps([thread_id, user_text, assistant_text], ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"ga-turn-{digest[:24]}"


def _title_from(agent: Any, user_text: str) -> str:
    task_dir = getattr(agent, "task_dir", "") or ""
    if task_dir:
        name = Path(str(task_dir)).name
        if name:
            return f"GenericAgent: {name}"
    first = " ".join(user_text.strip().split())[:80]
    return f"GenericAgent: {first or time.strftime('%Y-%m-%d %H:%M:%S')}"


class NmemSessionArchive:
    """Append completed GenericAgent turns to an nmem thread."""

    def __init__(self, client: Optional[NmemClient] = None, thread_id: Optional[str] = None):
        self.client = client or NmemClient()
        self.thread_id = thread_id
        self.created = False
        self.last_result: Dict[str, Any] = {}

    def save_turn(self, agent: Any, user_content: Any, assistant_content: Any) -> Dict[str, Any]:
        user_text = _clip(user_content, MAX_USER_CHARS)
        assistant_text = _clip(assistant_content, MAX_ASSISTANT_CHARS)
        if not user_text.strip() and not assistant_text.strip():
            self.last_result = {"saved": False, "reason": "empty_turn", "thread_id": self.thread_id}
            return self.last_result

        if not self.thread_id:
            self.thread_id = _stable_thread_id(agent)

        messages: List[Dict[str, str]] = []
        if user_text.strip():
            messages.append({"role": "user", "content": user_text})
        if assistant_text.strip():
            messages.append({"role": "assistant", "content": assistant_text})

        count = self.client.get_thread_message_count(self.thread_id)
        if count is None:
            returned_thread_id = self.client.create_thread(
                self.thread_id,
                _title_from(agent, user_text),
                messages,
                source=SOURCE,
            )
            self.thread_id = returned_thread_id or self.thread_id
            result = {"saved": True, "operation": "create", "thread_id": self.thread_id, "messages_added": len(messages)}
        else:
            result = self.client.append_thread(
                self.thread_id,
                messages,
                deduplicate=True,
                idempotency_key=_turn_idempotency_key(self.thread_id, user_text, assistant_text),
            )
            result.update({"saved": True, "operation": "append", "thread_id": self.thread_id})

        try:
            after_count = self.client.get_thread_message_count(self.thread_id)
        except Exception:
            after_count = None
        result["verified_message_count"] = after_count
        self.last_result = result
        return result


def _archive_for(agent: Any, client_factory=NmemClient) -> NmemSessionArchive:
    archive = _ARCHIVES.get(agent)
    if archive is None:
        archive = NmemSessionArchive(client=client_factory(), thread_id=getattr(agent, "_nmem_thread_id", None))
        _ARCHIVES[agent] = archive
        setattr(agent, "_nmem_thread_id", archive.thread_id)
    return archive


def install(agent_class: Optional[type] = None, client_factory=NmemClient) -> bool:
    """Install the central queue hook on GenericAgent/GeneraticAgent.

    The patched method keeps original behavior first, then saves only completed
    user/assistant turns when `query` is present and `ret` is a string.
    """
    if agent_class is None:
        import agentmain  # type: ignore
        agent_class = getattr(agentmain, "GeneraticAgent", None) or getattr(agentmain, "GenericAgent")

    if getattr(agent_class, "_nmem_session_hook_installed", False):
        return True

    original_put_task = getattr(agent_class, "put_task", None)
    if original_put_task is None:
        return False

    def put_task_with_nmem(self, query, ret, *args, **kwargs):
        original_result = original_put_task(self, query, ret, *args, **kwargs)
        if query is not None and isinstance(ret, str) and ret.strip():
            archive = _archive_for(self, client_factory=client_factory)
            try:
                save_result = archive.save_turn(self, query, ret)
                setattr(self, "_nmem_last_session_save", save_result)
                setattr(self, "_nmem_thread_id", archive.thread_id)
            except Exception as exc:  # non-fatal for GenericAgent runtime
                setattr(self, "_nmem_last_session_save_error", repr(exc))
        return original_result

    put_task_with_nmem._original_put_task = original_put_task  # type: ignore[attr-defined]
    agent_class.put_task = put_task_with_nmem
    agent_class._nmem_session_hook_installed = True
    return True
