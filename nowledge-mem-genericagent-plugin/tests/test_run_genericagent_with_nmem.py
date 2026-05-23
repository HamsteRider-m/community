import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import run_genericagent_with_nmem as runner


class FakeAgent:
    def __init__(self):
        self.llm_no = None
        self.verbose = None

    def next_llm(self, llm_no):
        self.llm_no = llm_no

    def run(self):
        return None


class FakeAgentMain:
    class GenericAgent(FakeAgent):
        pass


def test_wrapper_installs_session_hook_on_created_agent(monkeypatch, tmp_path):
    (tmp_path / "agentmain.py").write_text("# fake GenericAgent root\n")
    installed = []

    monkeypatch.setattr(runner, "_load_agentmain", lambda ga_root: FakeAgentMain)
    monkeypatch.setattr(runner.threading, "Thread", lambda target, daemon: type("T", (), {"start": lambda self: None})())
    monkeypatch.setattr(runner.genericagent_session_hook, "install", lambda agent: installed.append(agent) or True)
    monkeypatch.setattr(runner, "_run_task", lambda agentmain, agent, args: None)

    monkeypatch.setattr(sys, "argv", ["run_genericagent_with_nmem.py", "--ga-root", str(tmp_path), "--skip-nmem-check", "--task", "demo", "--nobg"])
    assert runner.main() == 0
    assert len(installed) == 1
    assert isinstance(installed[0], FakeAgent)
