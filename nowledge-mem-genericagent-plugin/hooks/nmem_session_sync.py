import hashlib
import json
import os
import queue
import socket
import subprocess
import threading
import time
import traceback
import weakref
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parent
TRANSCRIPT_DIR = PLUGIN_DIR / "transcripts"
LOG_FILE = PLUGIN_DIR / "nmem_session_sync.log"
DEFAULT_SOURCE = "genericagent"

_archives = weakref.WeakKeyDictionary()


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _log(message):
    PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{_now()}] {message}\n")


def _json(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _short_title(text):
    clean = " ".join(str(text).split())
    return clean[:80] or "GenericAgent session"


def _clip(text, limit):
    if not limit:
        return str(text)
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[truncated by GA_NMEM_MAX_ASSISTANT_CHARS={limit}]"


def _thread_id():
    base = f"ga-{socket.gethostname()}-{os.getpid()}-{int(time.time())}"
    digest = hashlib.sha1(base.encode()).hexdigest()[:10]
    return f"{base}-{digest}".replace(".", "-")


class NmemThreadArchive:
    def __init__(self, runner=None, thread_id=None, source=None, space=None, transcript_dir=None):
        self.runner = runner or self._run
        self.thread_id = thread_id or os.environ.get("GA_NMEM_THREAD_ID") or _thread_id()
        self.source = source or os.environ.get("GA_NMEM_SOURCE", DEFAULT_SOURCE)
        self.space = space if space is not None else os.environ.get("GA_NMEM_SPACE", "")
        self.transcript_dir = Path(transcript_dir or TRANSCRIPT_DIR)
        self.created = False
        self.turn = 0
        self.max_assistant_chars = int(os.environ.get("GA_NMEM_MAX_ASSISTANT_CHARS", "0") or "0")

    def save_turn(self, user_content, assistant_content, source="user", images=None):
        if os.environ.get("GA_NMEM_SESSION_SYNC", "1") in ("0", "false", "False", "no"):
            return {"status": "disabled"}

        self.turn += 1
        user_text = str(user_content)
        if images:
            user_text += f"\n\n[images: {len(images)}]"
        assistant_text = _clip(assistant_content, self.max_assistant_chars)
        messages = [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ]
        self._write_local(messages, source)

        if not self.created:
            result = self._import_thread(messages, title=_short_title(user_text))
            self.created = result.get("returncode") == 0
            return result
        return self._append_thread(messages)

    def _write_local(self, messages, source):
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        path = self.transcript_dir / f"{self.thread_id}.jsonl"
        record = {"time": _now(), "source": source, "turn": self.turn, "messages": messages}
        with path.open("a", encoding="utf-8") as f:
            f.write(_json(record) + "\n")

    def _import_thread(self, messages, title):
        cmd = ["t", "import", "--id", self.thread_id, "-s", self.source, "-t", title, "-m", _json(messages)]
        if self.space:
            cmd = ["t", "import", "--space", self.space, "--id", self.thread_id, "-s", self.source, "-t", title, "-m", _json(messages)]
        return self.runner(cmd)

    def _append_thread(self, messages):
        key_src = f"{self.thread_id}:{self.turn}:{_json(messages)}"
        key = hashlib.sha1(key_src.encode()).hexdigest()
        return self.runner(["t", "append", self.thread_id, "-m", _json(messages), "--idempotency-key", key])

    def _run(self, args):
        proc = subprocess.run(["nmem"] + args, text=True, capture_output=True, timeout=60)
        result = {"returncode": proc.returncode}
        if proc.stdout.strip():
            result["stdout"] = proc.stdout.strip()
        if proc.stderr.strip():
            result["stderr"] = proc.stderr.strip()
        if proc.returncode != 0:
            _log(f"nmem failed: args={args!r} result={result!r}")
        return result


class SyncQueue(queue.Queue):
    def __init__(self, archive, query, source, images):
        super().__init__()
        self.archive = archive
        self.query = query
        self.source = source
        self.images = images or []

    def put(self, item, block=True, timeout=None):
        result = super().put(item, block=block, timeout=timeout)
        if isinstance(item, dict) and "done" in item and item.get("source") != "system":
            threading.Thread(target=self._sync_done, args=(item["done"],), daemon=True).start()
        return result

    def _sync_done(self, assistant_content):
        try:
            result = self.archive.save_turn(self.query, assistant_content, source=self.source, images=self.images)
            if os.environ.get("GA_NMEM_SESSION_SYNC_VERBOSE"):
                _log(f"synced turn: thread_id={self.archive.thread_id} result={result!r}")
        except Exception:
            _log("sync exception:\n" + traceback.format_exc())


def get_archive(agent):
    archive = _archives.get(agent)
    if archive is None:
        archive = NmemThreadArchive()
        _archives[agent] = archive
        setattr(agent, "_nmem_thread_id", archive.thread_id)
    return archive


def install(agent_class=None):
    if agent_class is None:
        import agentmain
        agent_class = agentmain.GeneraticAgent
    if getattr(agent_class, "_nmem_session_sync_installed", False):
        return False

    original_put_task = agent_class.put_task

    def put_task_with_nmem(self, query, source="user", images=None):
        archive = get_archive(self)
        display_queue = SyncQueue(archive, query, source, images or [])
        self.task_queue.put({"query": query, "source": source, "images": images or [], "output": display_queue})
        return display_queue

    put_task_with_nmem._original_put_task = original_put_task
    agent_class.put_task = put_task_with_nmem
    agent_class._nmem_session_sync_installed = True
    _log(f"installed for {agent_class.__module__}.{agent_class.__name__}")
    return True


if __name__ == "__main__":
    print("nmem_session_sync is a GenericAgent local hook. Use run_agentmain.py or run_launch.sh.")
