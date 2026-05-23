#!/usr/bin/env python3
"""Launch GenericAgent with the Nowledge Mem plugin enabled.

Usage:
  python run_genericagent_with_nmem.py --ga-root /path/to/GenericAgent --task demo --input "..."
  python run_genericagent_with_nmem.py --ga-root /path/to/GenericAgent --reflect watcher.py
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import genericagent_nmem

try:
    from src import genericagent_session_hook
except ImportError:  # pragma: no cover - direct script execution from plugin root
    import genericagent_session_hook  # type: ignore


def _check_nmem_ready() -> None:
    nmem = shutil.which("nmem")
    if not nmem:
        raise SystemExit(
            "nmem is required but was not found on PATH. Install/configure Nowledge Mem before updating GenericAgent."
        )
    try:
        proc = subprocess.run(
            [nmem, "status"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        raise SystemExit(f"nmem status failed before GenericAgent startup: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"nmem is not ready; `nmem status` exited {proc.returncode}: {detail}")
    print("[nmem] status ok", file=sys.stderr)


def _load_agentmain(ga_root: Path):
    sys.path.insert(0, str(ga_root))
    spec = importlib.util.spec_from_file_location("agentmain", ga_root / "agentmain.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load agentmain.py from {ga_root}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["agentmain"] = module
    spec.loader.exec_module(module)
    
    # Install the patch immediately after exec_module, before GenericAgent is created
    # This ensures get_system_prompt is patched before agent.run() is called
    genericagent_nmem.install(module)
    return module


def _run_task(agentmain, agent, args):
    agent.peer_hint = False
    task_dir = Path(agentmain.script_dir) / "temp" / args.task
    agent.task_dir = str(task_dir)
    task_dir.mkdir(parents=True, exist_ok=True)
    input_file = task_dir / "input.txt"
    if args.input:
        for path in glob.glob(str(task_dir / "output*.txt")):
            os.remove(path)
        input_file.write_text(args.input, encoding="utf-8")
    if (history := agentmain.consume_file(str(task_dir), "_history.json")):
        agent.llmclient.backend.history = json.loads(history)
    raw = input_file.read_text(encoding="utf-8")
    nround = ""
    while True:
        dq = agent.put_task(raw, source="task")
        while "done" not in (item := dq.get(timeout=300)):
            if "next" in item and random.random() < 0.95:
                (task_dir / f"output{nround}.txt").write_text(item.get("next", ""), encoding="utf-8")
        (task_dir / f"output{nround}.txt").write_text(item["done"] + "\n\n[ROUND END]\n", encoding="utf-8")
        agentmain.consume_file(str(task_dir), "_stop")
        for _ in range(300):
            time.sleep(2)
            if (raw := agentmain.consume_file(str(task_dir), "reply.txt")):
                break
        else:
            break
        nround = nround + 1 if isinstance(nround, int) else 1


def _run_reflect(agentmain, agent, reflect_path: str):
    agent.peer_hint = False
    spec = importlib.util.spec_from_file_location("reflect_script", reflect_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load reflect script: {reflect_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mtime = os.path.getmtime(reflect_path)
    print(f"[Reflect] loaded {reflect_path}")
    while True:
        if os.path.getmtime(reflect_path) != mtime:
            try:
                spec.loader.exec_module(mod)
                mtime = os.path.getmtime(reflect_path)
                print("[Reflect] reloaded")
            except Exception as exc:
                print(f"[Reflect] reload error: {exc}")
        time.sleep(getattr(mod, "INTERVAL", 5))
        try:
            task = mod.check()
        except Exception as exc:
            print(f"[Reflect] check() error: {exc}")
            continue
        if task and task == "/exit":
            break
        if task is None:
            continue
        print(f"[Reflect] triggered: {task[:80]}")
        dq = agent.put_task(task, source="reflect")
        while "done" not in (item := dq.get(timeout=300)):
            if "next" in item:
                print(item["next"])
        print(item["done"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GenericAgent with Nowledge Mem context injection")
    parser.add_argument("--ga-root", default=os.environ.get("GENERICAGENT_ROOT", "."), help="GenericAgent repository root")
    parser.add_argument("--task", metavar="IODIR", help="GenericAgent one-shot file IO task")
    parser.add_argument("--reflect", metavar="SCRIPT", help="GenericAgent reflect script")
    parser.add_argument("--input", help="prompt for --task")
    parser.add_argument("--llm_no", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--nobg", action="store_true")
    parser.add_argument(
        "--skip-nmem-check",
        action="store_true",
        help="skip the startup `nmem status` health check",
    )
    args = parser.parse_args()

    if not args.skip_nmem_check:
        _check_nmem_ready()

    ga_root = Path(args.ga_root).expanduser().resolve()
    if not (ga_root / "agentmain.py").exists():
        raise SystemExit(f"agentmain.py not found under {ga_root}")

    if args.task and not args.nobg:
        cmd = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--nobg"]
        task_dir = ga_root / "temp" / args.task
        task_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            cmd,
            cwd=str(ga_root),
            creationflags=0x08000000 if platform.system() == "Windows" else 0,
            stdout=open(task_dir / "stdout.log", "w", encoding="utf-8"),
            stderr=open(task_dir / "stderr.log", "w", encoding="utf-8"),
        )
        print(proc.pid)
        return 0

    agentmain = _load_agentmain(ga_root)
    agent = agentmain.GenericAgent()
    genericagent_session_hook.install(agent)
    agent.next_llm(args.llm_no)
    agent.verbose = args.verbose
    threading.Thread(target=agent.run, daemon=True).start()

    if args.task:
        _run_task(agentmain, agent, args)
    elif args.reflect:
        _run_reflect(agentmain, agent, args.reflect)
    else:
        print("Nowledge Mem plugin installed. Use --task or --reflect to run GenericAgent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
