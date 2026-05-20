# nowledge-mem-genericagent-plugin

**Nowledge Memory (nmem) integration for GenericAgent** — Seamlessly inject working memory, search history, and distilled insights into GenericAgent's system prompt without modifying source code.

[![Status](https://img.shields.io/badge/status-SSOT%20docs%20updated-yellow)]() [![Session%20Save](https://img.shields.io/badge/session%20save-central%20hook%20planned-orange)]() [![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()

---

## Overview

This plugin enables GenericAgent to leverage [Nowledge Memory (nmem)](https://github.com/nowledge-co/nmem) for persistent context management across sessions. It uses **monkey patching** to inject nmem's working memory into the system prompt at runtime, preserving GenericAgent's source code integrity.

> **SSOT status (2026-05-20)**: This directory is the source of truth for the GenericAgent × nmem community integration; see [SESSION_SAVE_SSOT.md](./SESSION_SAVE_SSOT.md) for the session-save decision record. Working-memory injection / AutoRecall are the usable parts. Automatic session-save must be implemented through GenericAgent's central queue completion point (`GenericAgent.run`, after `done` is emitted and before/around `task_done()`), not through the out-of-process watcher. `src/session_watcher.py` and manual scan tools are retained only as fallback/backfill until the central hook is implemented and tested.

### Key Features

- **Zero Source Code Modification**: Uses Python monkey patching to wrap `get_system_prompt()`
- **Pure API Architecture**: Direct HTTP API calls, no CLI dependencies
- **Automatic Working Memory Injection**: Loads nmem working memory at session start
- **Session Save (planned)**: central GenericAgent completion hook is the intended automatic-save path; watcher/manual scan are fallback/backfill only
- **Hybrid-Aware Operating Model**: Adapts to GenericAgent's autonomous + user-driven workflow
- **Graceful Degradation**: Falls back to plain text if JSON parsing fails
- **Validated Scope**: working-memory injection and API client behavior are covered by tests; automatic session-save still requires implementation and end-to-end write acceptance

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  GenericAgent Session Start                                 │
│  ↓                                                           │
│  agentmain.get_system_prompt() [PATCHED]                   │
│  ↓                                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. Call original get_system_prompt()                │   │
│  │    → Returns base system prompt                      │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ 2. Call build_prompt_block()                        │   │
│  │    ├─ Read working memory (HTTP API)                │   │
│  │    │  GET /agent/working-memory                      │   │
│  │    └─ Format as prompt block                        │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ 3. Append nmem block to original prompt             │   │
│  │    → Returns: original_prompt + nmem_block          │   │
│  └─────────────────────────────────────────────────────┘   │
│  ↓                                                           │
│  Agent receives enriched prompt with nmem context          │
└─────────────────────────────────────────────────────────────┘
```

### Components

**AutoRecall (Working Memory Injection)**
- **`genericagent_nmem.py`**: Core plugin / working-memory injection
  - `install()`: monkey patches `agentmain.get_system_prompt()`
  - `build_prompt_block()`: constructs nmem context block
  - `read_working_memory()`: fetches working memory through the nmem API client
  - `export_handoff()`: manual handoff/export helper; not automatic session-save acceptance

- **`wrapper.py`**: Standalone wrapper script (optional)
  - Imports and installs the plugin before launching GenericAgent
  - Usage: `python wrapper.py` (instead of `ga`)

**Session Save (Conversation Archiving)**
- **`src/session_save.py`**: Core session save module
  - `SessionParser`: Parses `model_responses_*.txt` log files
  - `NmemClient`: Direct HTTP API client (bypasses CLI limitations)
  - Handles GenericAgent's unique log format (Prompt/Response sections)

- **`src/session_save_cli.py`**: Manual session save tool
  - Save specific log files: `python session_save_cli.py /path/to/log.txt`
  - Batch save all logs: `python session_save_cli.py --all`

- **`src/session_watcher.py`**: Legacy fallback/backfill watcher
  - Watches `temp/model_responses/` for new/modified logs
  - Not the primary automatic-save mechanism
  - Prefer the planned central GenericAgent completion hook for automatic save

**Documentation**
- **`AGENTS.md`**: Operating model documentation (236 lines)
  - When to read/search/distill/save
  - GenericAgent-specific adaptation guidelines
  - Failure handling and degradation strategies

---

## Installation

### Prerequisites

- Python 3.10+
- [Nowledge Memory (nmem)](https://github.com/nowledge-co/nmem) installed and running
- GenericAgent installed

### Setup

1. **Clone the repository**:
   ```bash
   cd /path/to/GenericAgent/temp
   git clone https://github.com/YOUR_USERNAME/community.git
   cd community/nowledge-mem-genericagent-plugin
   ```

2. **Verify nmem is running**:
   ```bash
   # Check if nmem server is accessible
   curl http://localhost:3721/health
   # Should return: {"status":"ok"}
   ```

3. **Install the plugin** (choose one method):

   **Method A: Wrapper Script** (Recommended)
   ```bash
   # Use wrapper.py instead of 'ga' command
   python wrapper.py
   ```

   **Method B: Manual Import**
   ```python
   # Add to GenericAgent's startup script or config
   import sys
   sys.path.insert(0, '/path/to/nowledge-mem-genericagent-plugin')
   import genericagent_nmem
   genericagent_nmem.install()
   ```

   **Method C: Environment Variable**
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   export PYTHONPATH="/path/to/nowledge-mem-genericagent-plugin:$PYTHONPATH"
   
   # Then in GenericAgent's startup:
   import genericagent_nmem
   genericagent_nmem.install()
   ```

---

## Usage

### Basic Workflow

1. **Start GenericAgent** (with plugin installed):
   ```bash
   python wrapper.py  # or 'ga' if manually integrated
   ```

2. **Working Memory is automatically injected** into the system prompt:
   ```
   [Nowledge Mem / nmem integration for GenericAgent]
   
   Integration status: working-memory-loaded
   
   [Nowledge Working Memory]
   # Working Memory — 2026-05-20
   
   ## Focus Areas
   - Task A: In progress, blocked on X
   - Task B: Completed, see distilled note #123
   ...
   ```

3. **Agent can reference nmem context** in responses:
   - "Based on the working memory, Task A is blocked on X..."
   - "I see from the distilled notes that we tried approach Y before..."

4. **Session Save status**:

   Automatic session-save is implemented by the in-process central completion hook in `src/genericagent_session_hook.py`. The hook patches GenericAgent's central `put_task(query, ret)` path, preserves original queue/frontend behavior first, then saves completed user/assistant turns to nmem and verifies the saved thread by readback message count.

   Install the session hook alongside the working-memory plugin before GenericAgent starts handling frontend traffic:
   ```python
   import genericagent_nmem
   genericagent_nmem.install()

   from src import genericagent_session_hook
   genericagent_session_hook.install()
   ```

   Fallback/backfill tools remain available for historical logs only:
   ```bash
   cd /path/to/nowledge-mem-genericagent-plugin
   python src/session_save_cli.py --help
   python src/session_watcher.py  # legacy fallback; not the primary automatic-save mechanism
   ```

   Acceptance evidence in this repo:
   - `tests/test_genericagent_session_hook.py`: create/append/readback and central hook patch behavior
   - `tests/test_session_save.py`: parser/manual backfill API behavior
   - Live nmem telemetry acceptance remains environment-gated: run with a reachable nmem API and preserve readback evidence.

### Advanced: MCP Integration

If using [Model Context Protocol (MCP)](https://modelcontextprotocol.io/):

1. **Configure MCP server** in `~/.config/nmem/config.toml`:
   ```toml
   [mcp]
   enabled = true
   server_command = "npx"
   server_args = ["-y", "@nowledgeco/mcp-server-nmem"]
   ```

2. **Agent can use MCP tools**:
   - `nmem_search`: Search memory by query
   - `nmem_distill`: Create distilled notes
   - `nmem_save`: Save to working memory

---

## Configuration

### Environment Variables

- `NMEM_BASE_URL`: Nowledge Mem API base URL (default depends on local nmem configuration)
- `NMEM_TIMEOUT`: HTTP/API timeout in seconds

### Plugin Behavior

Edit `genericagent_nmem.py` to customize:

```python
# Adjust working memory read timeout / API client behavior
client = NmemClient(timeout=15)

# Change prompt block format
def build_prompt_block() -> str:
    # Customize the output format here
    ...
```

---

## Testing

### Run Tests

```bash
# Install test dependencies in an isolated environment
python -m venv venv
source venv/bin/activate  # or 'venv\Scripts\activate' on Windows
pip install -e .
pip install pytest pytest-cov pytest-mock

# Run the current test suite
pytest tests/ -v

# Optional coverage for the current plugin code
pytest tests/ -v --cov=genericagent_nmem --cov-report=term-missing

# Current test files
pytest tests/test_genericagent_nmem_api.py -v  # working-memory/API client behavior
pytest tests/test_session_save.py -v          # session-save parser/selection helpers
```

### Test Coverage / Acceptance Status

- **Current test files in this directory**:
  - `test_genericagent_nmem_api.py`: working-memory API client behavior and install wrapper behavior
  - `test_session_save.py`: session-save helper/parser behavior

- **Not yet accepted as production-ready**:
  - Automatic session-save through GenericAgent's central completion hook still needs implementation.
  - End-to-end nmem write/readback acceptance is still pending.
  - Coverage percentages must be generated from the current checkout; do not reuse historical CLI-test coverage numbers.

---

## Operating Model

See [AGENTS.md](./AGENTS.md) for detailed guidelines on:

- **When to read working memory**: Session start, user request, idle resume
- **When to search**: Strong signals (explicit request, knowledge gap) vs. weak signals (skip)
- **When to distill**: After search, avoid duplication
- **When to save**: Session end, major milestone, handoff
- **Failure handling**: Graceful degradation, fallback strategies

### GenericAgent-Specific Adaptations

1. **Hybrid Operating Model**: GenericAgent alternates between autonomous execution and user-driven tasks
   - Read working memory at session start (not every turn)
   - Search on explicit user request or knowledge gap
   - Save at session end or major milestone

2. **No Source Code Modification**: Uses monkey patching instead of hooks
   - Install via `wrapper.py` or manual import
   - Preserves GenericAgent's update path

3. **Graceful Degradation**: Falls back if nmem is unavailable
   - Plugin returns empty string if CLI fails
   - Agent continues without nmem context

---

## Troubleshooting

### Issue: "nmem CLI not found"

**Solution**: Ensure `m` is in PATH:
```bash
which m
# If not found, install nmem:
pip install nowledge-mem
```

### Issue: "Working memory is empty"

**Cause**: No working memory file exists yet.

**Solution**: Create initial working memory:
```bash
m wm write "# Working Memory\n\n## Focus Areas\n- Task 1: Description"
```

### Issue: "Monkey patch not applied"

**Cause**: Plugin installed after `agentmain` module loaded.

**Solution**: Ensure plugin is imported **before** GenericAgent starts:
```python
# In wrapper.py or startup script:
import genericagent_nmem
genericagent_nmem.install()  # Must be called before agentmain import
```

### Issue: "Automatic session-save did not run"

**Checklist**:
1. Ensure `genericagent_session_hook.install()` ran before frontend traffic starts.
2. Confirm the completed event called `put_task(query, ret)` with a non-empty assistant string.
3. Inspect `agent._nmem_last_session_save` or `agent._nmem_last_session_save_error` for save/readback diagnostics.
4. Use manual/backfill tools only for historical logs; do not promote the legacy watcher as the primary path.

---

## Development

### Project Structure

```
nowledge-mem-genericagent-plugin/
├── genericagent_nmem.py    # Core plugin / working-memory injection
├── wrapper.py              # Standalone wrapper script
├── AGENTS.md               # Operating model documentation (236 lines)
├── README.md               # This file
├── pyproject.toml          # Package metadata
├── src/genericagent_session_hook.py  # Central completion hook for automatic session-save
├── tests/                 # Unit/API tests including session-save hook acceptance
└── htmlcov/                # Coverage report (generated)
```

### Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/my-feature`
3. **Write tests**: include acceptance evidence for any new capability claims
4. **Run tests**: `pytest tests/ -v`
5. **Submit PR**: link the issue and include test/readback evidence

---

## Comparison with Other Plugins

| Feature | GenericAgent | Codex | Droid |
|---------|--------------|-------|-------|
| Integration Method | Monkey Patch | Hooks | Hooks |
| Source Code Modification | ❌ No | ✅ Yes | ✅ Yes |
| Working Memory Injection | ✅ Auto | ✅ Auto | ✅ Auto |
| Session Save | 🔧 Central hook planned; watcher fallback/backfill | ✅ Auto (Stop hook) | ✅ Auto |
| MCP Support | ✅ Yes | ✅ Yes | ✅ Yes |
| Test Evidence | API/helper tests; automatic session-save E2E pending | N/A | N/A |

---

## Roadmap

- [ ] **Automatic Session Save**: Implement the GenericAgent central completion hook (`GenericAgent.run`) and verify write/readback acceptance
- [ ] **AutoRecall**: Proactive memory search based on task context
- [ ] **Performance Optimization**: Cache working memory for repeated reads
- [ ] **Configuration File**: Support `~/.config/genericagent-nmem/config.toml`

---

## License

MIT License - See [LICENSE](../LICENSE) for details.

---

## References

- [Nowledge Memory (nmem)](https://github.com/nowledge-co/nmem)
- [GenericAgent Documentation](https://datawhalechina.github.io/hello-generic-agent/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Codex Plugin (Reference Implementation)](https://github.com/nowledge-co/community/tree/main/codex)

---

## Support

- **Issues**: [GitHub Issues](https://github.com/nowledge-co/community/issues)
- **Discussions**: [GitHub Discussions](https://github.com/nowledge-co/community/discussions)
- **Documentation**: [AGENTS.md](./AGENTS.md)

---

**Status**: ⚠️ Partial / SSOT updated | **Version**: 0.1.1 | **Last Updated**: 2026-05-20
