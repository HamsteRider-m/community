# Nowledge Mem — GenericAgent Plugin

> Your personal knowledge graph, built into GenericAgent. The agent loads your working memory, searches past sessions, retrieves SOPs, and saves every conversation — without you asking.

Switch between GenericAgent, your IDE, and other tools without losing context. Decisions you made last week, procedures you discovered yesterday, the architecture rationale from three months ago: it's all there when you need it.

## What You Get

**Automatic (no action needed):**

- **Working Memory briefing** loaded at every agent start and resume
- **AutoRecall** — searches your working memory, recent threads, and distilled memories on every turn
- **SOP index injection** — relevant memory SOPs (skill_search, plan_sop, web_setup_sop, …) are surfaced in the system prompt so the agent knows what capabilities are available
- **Deduplicated global memory** — prevents redundant `get_global_memory()` instructions from piling up across turns
- **Session capture** — every conversation saved to your knowledge graph after the agent finishes responding

**Agent-initiated (the agent acts on its own):**

- **Search Memory** — searches both distilled memories and prior sessions when continuity matters
- **Save Thread** — captures the full transcript to Nowledge Mem
- **Read Working Memory** — loads your daily context briefing

## Install

### Prerequisites

`nmem` CLI must be in your PATH:

```bash
pip install nmem-cli    # or: pipx install nmem-cli
nmem status             # verify connection
```

### Option A: Manual Install (current)

Copy the hook files into GenericAgent's `plugins/` directory:

```bash
# Clone the community repo
git clone https://github.com/nowledge-co/community.git /tmp/nowledge-community

# Copy hooks to GenericAgent
cp /tmp/nowledge-community/nowledge-mem-genericagent-plugin/hooks/*.py \
   /path/to/GenericAgent/plugins/

# Restart GenericAgent
```

The hooks auto-load on agent start — no config files, no monkey-patching.

### Option B: Marketplace (coming soon)

```
ga plugin marketplace add nowledge-co/community
ga plugin install nowledge-mem@nowledge-community
```

### Verify

Start GenericAgent and observe the log output:

```
[NMEM] AutoRecall plugin registered for: agent_before, turn_before, llm_before
[NMEM] Session sync plugin registered for: agent_after
```

Or ask the agent: "What was I working on?" It should respond with your Working Memory briefing.

## How It Works

GenericAgent uses a native Python hook system (`plugins/hooks.py`). Hook files placed in `GenericAgent/plugins/` are auto-discovered and registered at startup.

### Lifecycle Hooks

| Event | Trigger | What happens |
|-------|---------|-------------|
| `agent_before` | Agent starts or resumes | Injects Working Memory, SOP index, and AutoRecall context into system prompt |
| `turn_before` | Every user message | Pre-loads relevant memories and threads for the current query |
| `llm_before` | Before each LLM call | Strips redundant `get_global_memory()` injections (keeps first, removes duplicates) |
| `agent_after` | Agent finishes responding | Captures the full session transcript to Nowledge Mem |

### Plugin Files

| File | Hooks | Responsibility |
|------|-------|---------------|
| `nmem_auto_recall.py` | `agent_before`, `turn_before`, `llm_before` | Working Memory injection, AutoRecall search, SOP index, deduplication |
| `nmem_session_sync.py` | `agent_after` | Session transcript capture and thread saving |

### Architecture

```
agent_loop.py
    │
    ├─ agent_before  → nmem_auto_recall: inject WM + SOP index + AutoRecall prompt
    ├─ turn_before   → nmem_auto_recall: pre-search memories & threads
    ├─ llm_before    → nmem_auto_recall: deduplicate global_memory blocks
    └─ agent_after   → nmem_session_sync: save transcript to nmem
```

All hooks receive `ctx = locals()` from `agent_loop.py`, giving them access to `messages`, `handler`, and the full agent context. No monkey-patching, no `.omx/` injection directories.

## Spaces

Spaces are optional. To keep GenericAgent in its own project lane, set the environment variable before starting:

```bash
NMEM_SPACE="GenericAgent"
```

The session-start Working Memory read, AutoRecall searches, and transcript capture will then stay in that space automatically.

Shared spaces, default retrieval, and agent guidance still live in Mem's own space profile. GenericAgent does not need a second plugin-local space config.

## Remote Mem

If your Nowledge Mem server runs on a different machine, configure the client once:

```bash
nmem config client set url https://mem.example.com
nmem config client set api-key nmem_your_key
```

The plugin reads the same `nmem` client config. You can also use environment variables (`NMEM_API_URL`, `NMEM_API_KEY`) for temporary overrides.

## Update

```bash
cd /path/to/GenericAgent/plugins

# Pull latest from community repo
git -C /tmp/nowledge-community pull
cp /tmp/nowledge-community/nowledge-mem-genericagent-plugin/hooks/*.py .

# Restart GenericAgent
```

## Troubleshooting

**nmem not found:**
```bash
pip install nmem-cli
# or
pipx install nmem-cli
```

**Server not running:**
Start the Nowledge Mem desktop app, or run `nmem serve` on your server.

**Check status:**
```bash
nmem status
```

**Hooks not loading:**
1. Verify files are in `GenericAgent/plugins/` (not a subdirectory)
2. Check GenericAgent log for `[NMEM]` messages
3. Ensure `nmem` is in PATH before starting GenericAgent

**Space not switching:**
```bash
nmem spaces list               # verify space exists
nmem spaces create "my-space"  # create if needed
NMEM_SPACE="my-space"          # set before launching agent
```

## Links

- [Nowledge Mem](https://mem.nowledge.co)
- [Documentation](https://mem.nowledge.co/docs)
- [GenericAgent](https://github.com/lsdefine/GenericAgent)
- [Community Integrations](https://github.com/nowledge-co/community)
- [Discord](https://nowled.ge/discord)

---

Made with care by [Nowledge Labs](https://nowledge-labs.ai)
