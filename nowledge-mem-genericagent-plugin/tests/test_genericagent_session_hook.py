import queue
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from genericagent_session_hook import NmemSessionArchive, install, make_turn_end_hook, _stable_thread_id


class FakeClient:
    def __init__(self):
        self.counts = {}
        self.created = []
        self.appended = []

    def get_thread_message_count(self, thread_id):
        return self.counts.get(thread_id)

    def create_thread(self, thread_id, title, messages, source=None):
        self.created.append((thread_id, title, messages, source))
        self.counts[thread_id] = len(messages)
        return thread_id

    def append_thread(self, thread_id, messages, deduplicate=True, idempotency_key=None):
        self.appended.append((thread_id, messages, deduplicate, idempotency_key))
        self.counts[thread_id] = self.counts.get(thread_id, 0) + len(messages)
        return {"messages_added": len(messages)}


class Response:
    def __init__(self, content):
        self.content = content


class FakeGenericAgent:
    """Matches current GenericAgent put_task signature enough for regression."""

    def __init__(self):
        self.task_queue = queue.Queue()

    def put_task(self, query, source="user", images=None):
        display_queue = queue.Queue()
        self.task_queue.put({"query": query, "source": source, "images": images or [], "output": display_queue})
        return display_queue


def test_archive_create_then_append():
    client = FakeClient()
    archive = NmemSessionArchive(client=client, thread_id="thread-1")
    agent = object()

    first = archive.save_turn(agent, "hello", "world")
    second = archive.save_turn(agent, "again", "answer")

    assert first["operation"] == "create"
    assert second["operation"] == "append"
    assert client.created[0][2] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    assert client.appended[0][1] == [
        {"role": "user", "content": "again"},
        {"role": "assistant", "content": "answer"},
    ]
    assert first["verified_message_count"] == 2
    assert second["verified_message_count"] == 4


def test_install_wraps_task_queue_and_saves_on_done_item():
    client = FakeClient()
    agent = FakeGenericAgent()

    assert install(agent, client_factory=lambda: client) is True
    assert getattr(agent.task_queue, "_nmem_task_queue_proxy") is True

    display_queue = agent.put_task("question", source="cli", images=["image.png"])
    task = agent.task_queue.get_nowait()
    assert task["query"] == "question"
    assert task["source"] == "cli"
    assert task["images"] == ["image.png"]
    assert task["output"] is not display_queue

    task["output"].put({"done": "answer", "source": "assistant"})

    assert display_queue.get_nowait() == {"done": "answer", "source": "assistant"}
    assert agent._nmem_last_session_save["saved"] is True
    assert agent._nmem_last_session_save["operation"] == "create"
    assert client.created[0][2] == [
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "answer"},
    ]


def test_install_is_idempotent_and_does_not_patch_put_task_signature():
    client = FakeClient()
    agent = FakeGenericAgent()
    original_put_task = type(agent).put_task

    assert install(agent, client_factory=lambda: client) is True
    assert install(agent, client_factory=lambda: client) is True
    assert getattr(agent.task_queue, "_nmem_task_queue_proxy") is True
    assert type(agent).put_task is original_put_task

    display_queue = agent.put_task("question", source="cli", images=["image.png"])
    assert isinstance(display_queue, queue.Queue)
    task = agent.task_queue.get_nowait()
    assert task["query"] == "question"
    assert task["output"] is not display_queue
    assert client.created == []


def test_hook_skips_empty_turn_context():
    client = FakeClient()
    agent = FakeGenericAgent()
    hook = make_turn_end_hook(agent, client_factory=lambda: client)

    assert hook({}) is None

    assert client.created == []
    assert not hasattr(agent, "_nmem_last_session_save")


def test_stable_thread_id_prefers_session_id_for_watcher_compatibility():
    agent = FakeGenericAgent()
    agent.session_id = "840360"

    assert _stable_thread_id(agent) == "ga-840360"


def test_stable_thread_id_sanitizes_session_id():
    agent = FakeGenericAgent()
    agent.session_id = "tg app/with spaces"

    assert _stable_thread_id(agent) == "ga-tg-app-with-spaces"
