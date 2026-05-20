import queue
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from genericagent_session_hook import NmemSessionArchive, install


class FakeClient:
    def __init__(self):
        self.counts = {}
        self.created = []
        self.appended = []

    def get_thread_message_count(self, thread_id):
        return self.counts.get(thread_id)

    def create_thread(self, thread_id, title, messages, source="genericagent"):
        self.created.append({"thread_id": thread_id, "title": title, "messages": messages, "source": source})
        self.counts[thread_id] = len(messages)
        return thread_id

    def append_thread(self, thread_id, messages, deduplicate=True, idempotency_key=None):
        self.appended.append({"thread_id": thread_id, "messages": messages, "deduplicate": deduplicate, "idempotency_key": idempotency_key})
        self.counts[thread_id] = self.counts.get(thread_id, 0) + len(messages)
        return {"messages_added": len(messages), "total_messages": self.counts[thread_id]}


class FakeAgent:
    def __init__(self):
        self.queue = queue.Queue()
        self.task_dir = "/tmp/ga-task-demo"

    def put_task(self, query, ret):
        self.queue.put((query, ret))
        return "original-return"


def test_archive_create_then_append_with_readback():
    client = FakeClient()
    agent = FakeAgent()
    archive = NmemSessionArchive(client=client, thread_id="ga-test")

    first = archive.save_turn(agent, "hello", "world")
    assert first["operation"] == "create"
    assert first["verified_message_count"] == 2
    assert client.created[0]["messages"] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]

    second = archive.save_turn(agent, "next", "answer")
    assert second["operation"] == "append"
    assert second["verified_message_count"] == 4
    assert client.appended[0]["idempotency_key"].startswith("ga-turn-")


def test_install_patches_put_task_and_preserves_original_behavior():
    client = FakeClient()

    class AgentForInstall(FakeAgent):
        pass

    assert install(AgentForInstall, client_factory=lambda: client) is True
    agent = AgentForInstall()
    result = agent.put_task("question", "answer")

    assert result == "original-return"
    assert agent.queue.get_nowait() == ("question", "answer")
    assert agent._nmem_last_session_save["saved"] is True
    assert agent._nmem_last_session_save["verified_message_count"] == 2
    assert len(client.created) == 1


def test_install_ignores_non_completed_or_empty_turns():
    client = FakeClient()

    class AgentForSkip(FakeAgent):
        pass

    assert install(AgentForSkip, client_factory=lambda: client) is True
    agent = AgentForSkip()
    agent.put_task("question", None)
    agent.put_task(None, "assistant-only")
    agent.put_task("question", "")

    assert client.created == []
    assert not hasattr(agent, "_nmem_last_session_save")
