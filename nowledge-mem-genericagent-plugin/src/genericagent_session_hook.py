"""GenericAgent in-process session-save bridge for nmem.

Current GenericAgent enqueues tasks as dictionaries containing ``query`` and an
``output`` queue, then posts the final assistant text to that display queue as a
``{"done": ...}`` item.  This module installs an instance-level task-queue proxy
that wraps each task display queue and archives the completed turn when the done
item is emitted.

The bridge does not modify GenericAgent source, does not patch the GenericAgent
class, and keeps ``put_task(query, source=..., images=...)`` semantics intact.
Filesystem watchers/backfill tools remain fallback only.
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


def _sanitize_thread_suffix(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in text)
    return safe.strip(".-_")[:80]


def _stable_thread_id(agent: Any) -> str:
    session_id = _sanitize_thread_suffix(getattr(agent, "session_id", "") or "")
    if session_id:
        return f"ga-{session_id}"

    task_dir = getattr(agent, "task_dir", "") or ""
    task_name = _sanitize_thread_suffix(Path(str(task_dir)).name if task_dir else "")
    if task_name:
        return f"ga-{task_name}"

    seed = task_dir or f"pid-{os.getpid()}-{id(agent)}"
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


def _context_get(context: Dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in context:
            return context[name]
    return None


def _extract_turn(context: Dict[str, Any]) -> tuple[Any, Any]:
    """Extract user and assistant text from a completed-task context.

    The task-queue bridge passes ``raw_query`` from the queued task and
    ``response`` from the display queue's final ``{"done": ...}`` item.
    The broader aliases keep the helper compatible with tests and future
    GenericAgent completion-hook shapes.
    """
    response = _context_get(context, "response", "assistant_response", "assistant")
    assistant_text = getattr(response, "content", response)
    user_text = _context_get(context, "raw_query", "query", "user_query", "user", "prompt")
    return user_text, assistant_text


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
        result["verified"] = after_count is not None and after_count >= 2
        self.last_result = result
        return result


def _archive_for(agent: Any, client_factory=NmemClient) -> NmemSessionArchive:
    archive = _ARCHIVES.get(agent)
    if archive is None:
        archive = NmemSessionArchive(client=client_factory(), thread_id=getattr(agent, "_nmem_thread_id", None))
        _ARCHIVES[agent] = archive
        setattr(agent, "_nmem_thread_id", archive.thread_id)
    return archive


def make_turn_end_hook(agent: Any, client_factory=NmemClient):
    """Create the non-fatal save callback used by the display-queue bridge."""

    def nmem_turn_end_hook(context: Dict[str, Any]):
        user_text, assistant_text = _extract_turn(context or {})
        if not (str(user_text or "").strip() or str(assistant_text or "").strip()):
            return None
        archive = _archive_for(agent, client_factory=client_factory)
        try:
            save_result = archive.save_turn(agent, user_text, assistant_text)
            setattr(agent, "_nmem_last_session_save", save_result)
            setattr(agent, "_nmem_thread_id", archive.thread_id)
            return save_result
        except Exception as exc:  # non-fatal for GenericAgent runtime
            setattr(agent, "_nmem_last_session_save_error", repr(exc))
            return None

    nmem_turn_end_hook._nmem_session_hook = True  # type: ignore[attr-defined]
    return nmem_turn_end_hook


class NmemDisplayQueueProxy:
    """Display-queue proxy that saves a turn when GenericAgent emits ``done``."""

    def __init__(self, inner: Any, agent: Any, user_text: Any, client_factory=NmemClient):
        self._inner = inner
        self._agent = agent
        self._user_text = user_text
        self._client_factory = client_factory
        self._nmem_saved = False

    def put(self, item: Any, *args: Any, **kwargs: Any):
        result = self._inner.put(item, *args, **kwargs)
        if isinstance(item, dict) and "done" in item and not self._nmem_saved:
            self._nmem_saved = True
            hook = make_turn_end_hook(self._agent, client_factory=self._client_factory)
            hook({"raw_query": self._user_text, "response": item.get("done"), "display_item": item})
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class NmemTaskQueueProxy:
    """Task-queue proxy that wraps per-task display queues before GA consumes them."""

    def __init__(self, inner: Any, agent: Any, client_factory=NmemClient):
        self._inner = inner
        self._agent = agent
        self._client_factory = client_factory

    def put(self, task: Any, *args: Any, **kwargs: Any):
        if isinstance(task, dict) and "output" in task and not getattr(task["output"], "_nmem_display_queue_proxy", False):
            task = dict(task)
            task["output"] = NmemDisplayQueueProxy(task["output"], self._agent, task.get("query"), self._client_factory)
            task["output"]._nmem_display_queue_proxy = True
        return self._inner.put(task, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def install(agent: Optional[Any] = None, client_factory=NmemClient) -> bool:
    """Install nmem session-save on a GenericAgent instance.

    The live GenericAgent runtime currently exposes task completion through each
    task's display queue rather than a public class hook.  We therefore replace
    only this agent instance's ``task_queue`` with a delegating proxy that wraps
    per-task display queues and saves when a ``done`` item is posted.  ``put_task``
    itself and the GenericAgent class remain untouched.
    """
    if agent is None:
        return False
    task_queue = getattr(agent, "task_queue", None)
    if task_queue is None:
        return False
    if getattr(task_queue, "_nmem_task_queue_proxy", False):
        setattr(agent, "_nmem_session_hook_installed", True)
        return True

    proxy = NmemTaskQueueProxy(task_queue, agent, client_factory=client_factory)
    proxy._nmem_task_queue_proxy = True  # type: ignore[attr-defined]
    setattr(agent, "task_queue", proxy)
    setattr(agent, "_nmem_session_hook_installed", True)
    return True
