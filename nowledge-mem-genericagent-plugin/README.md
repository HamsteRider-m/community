# nowledge-mem-genericagent-plugin

**Nowledge Memory (nmem) integration for GenericAgent** — Seamlessly inject working memory, search history, and distilled insights into GenericAgent's system prompt without modifying source code.

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)]() [![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)]() [![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()

---

## Overview

This plugin enables GenericAgent to leverage [Nowledge Memory (nmem)](https://github.com/nowledge-co/nmem) for persistent context management across sessions. It uses **monkey patching** to inject nmem's working memory into the system prompt at runtime, preserving GenericAgent's source code integrity.

### Key Features

- **Zero Source Code Modification**: Uses Python monkey patching to wrap `get_system_prompt()`
- **Automatic Working Memory Injection**: Loads nmem working memory at session start
- **Session Save**: Automatically saves GenericAgent conversations to nmem
- **Hybrid-Aware Operating Model**: Adapts to GenericAgent's autonomous + user-driven workflow
- **Graceful Degradation**: Falls back to plain text if JSON parsing fails
- **100% Test Coverage**: Comprehensive unit, integration, and end-to-end tests

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
│  │    ├─ Read working memory (m wm read --json)        │   │
│  │    ├─ Get nmem status (m status)                    │   │
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
- **`genericagent_nmem.py`**: Core plugin (84 lines)
  - `install()`: Monkey patches `agentmain.get_system_prompt()`
  - `build_prompt_block()`: Constructs nmem context block
  - `read_working_memory()`: Fetches working memory via CLI
  - `export_handoff()`: Saves session summary to nmem

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

- **`src/session_watcher.py`**: Automatic monitoring service
  - Watches `temp/model_responses/` for new/modified logs
  - Auto-saves completed sessions to nmem
  - Run as background service: `python session_watcher.py`

**Documentation**
- **`AGENTS.md`**: Operating model documentation (236 lines)
  - When to read/search/distill/save
  - GenericAgent-specific adaptation guidelines
  - Failure handling and degradation strategies

---

## Installation

### Prerequisites

- Python 3.10+
- [Nowledge Memory (nmem)](https://github.com/nowledge-co/nmem) installed and configured
- GenericAgent installed

### Setup

1. **Clone the repository**:
   ```bash
   cd /path/to/GenericAgent/temp
   git clone https://github.com/nowledge-co/community.git
   cd community/nowledge-mem-genericagent-plugin
   ```

2. **Verify nmem is installed**:
   ```bash
   m --version
   # Should output: nmem version x.x.x
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

4. **Session Save** — Archive conversations to nmem:

   **Manual Save (via export_handoff)**:
   ```python
   # In GenericAgent code or user command:
   from genericagent_nmem import export_handoff
   export_handoff("Completed feature X, next: test Y")
   ```

   **CLI Tool (save specific sessions)**:
   ```bash
   # Save a specific log file
   cd /path/to/nowledge-mem-genericagent-plugin
   python src/session_save_cli.py /path/to/GenericAgent/temp/model_responses/model_responses_887760.txt
   
   # Batch save all log files
   python src/session_save_cli.py --all
   ```

   **Automatic Monitoring (background service)**:
   ```bash
   # Start the watcher service
   cd /path/to/nowledge-mem-genericagent-plugin
   python src/session_watcher.py
   
   # The service will:
   # - Monitor temp/model_responses/ for new/modified logs
   # - Auto-save completed sessions to nmem
   # - Run continuously in the background
   ```

   **Verify saved sessions**:
   ```bash
   # List all threads
   m threads list
   
   # View a specific session
   m threads read ga-887760
   ```

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

- `NMEM_CLI_PATH`: Custom path to `m` CLI (default: searches PATH)
- `NMEM_TIMEOUT`: CLI command timeout in seconds (default: 10)

### Plugin Behavior

Edit `genericagent_nmem.py` to customize:

```python
# Adjust working memory read timeout
proc = _run_nmem(["wm", "read", "--json"], timeout=15)  # default: 10

# Change prompt block format
def build_prompt_block() -> str:
    # Customize the output format here
    ...
```

---

## Testing

### Run Tests

```bash
# Install test dependencies
python -m venv venv
source venv/bin/activate  # or 'venv\Scripts\activate' on Windows
pip install -e .
pip install pytest pytest-cov pytest-mock

# Run all tests with coverage
pytest tests/ -v --cov=genericagent_nmem --cov-report=term-missing

# Run specific test suites
pytest tests/test_cli.py -v          # CLI invocation tests
pytest tests/test_prompt.py -v       # Prompt building tests
pytest tests/test_install.py -v      # Monkey patching tests
pytest tests/test_e2e_wrapper.py -v  # End-to-end tests
```

### Test Coverage

- **Unit Tests** (56 tests):
  - `test_cli.py`: CLI command execution, error handling, timeouts
  - `test_prompt.py`: Working memory parsing, prompt formatting
  - `test_install.py`: Monkey patch behavior, global state management

- **End-to-End Tests** (5 tests):
  - `test_e2e_wrapper.py`: Real environment wrapper injection
  - Verifies: prompt modification, behavior preservation, CLI availability

**Current Coverage**: 100% (84/84 statements)

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

### Issue: "Tests fail with 'nmem CLI not found'"

**Expected**: End-to-end tests require nmem CLI in PATH. Unit tests mock CLI calls and should pass without nmem installed.

---

## Development

### Project Structure

```
nowledge-mem-genericagent-plugin/
├── genericagent_nmem.py    # Core plugin (84 lines)
├── wrapper.py              # Standalone wrapper script
├── AGENTS.md               # Operating model documentation (236 lines)
├── README.md               # This file
├── pyproject.toml          # Package metadata
├── tests/
│   ├── test_cli.py         # CLI invocation tests (20 tests)
│   ├── test_prompt.py      # Prompt building tests (20 tests)
│   ├── test_install.py     # Monkey patching tests (16 tests)
│   └── test_e2e_wrapper.py # End-to-end tests (5 tests)
└── htmlcov/                # Coverage report (generated)
```

### Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/my-feature`
3. **Write tests**: Maintain 100% coverage
4. **Run tests**: `pytest tests/ -v --cov=genericagent_nmem`
5. **Submit PR**: Include test results and coverage report

---

## Comparison with Other Plugins

| Feature | GenericAgent | Codex | Droid |
|---------|--------------|-------|-------|
| Integration Method | Monkey Patch | Hooks | Hooks |
| Source Code Modification | ❌ No | ✅ Yes | ✅ Yes |
| Working Memory Injection | ✅ Auto | ✅ Auto | ✅ Auto |
| Session Save | 🔧 Manual | ✅ Auto (Stop hook) | ✅ Auto |
| MCP Support | ✅ Yes | ✅ Yes | ✅ Yes |
| Test Coverage | 100% | N/A | N/A |

---

## Roadmap

- [ ] **Automatic Session Save**: Implement Stop hook equivalent without modifying source
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

**Status**: ✅ Production Ready | **Version**: 1.0.0 | **Last Updated**: 2026-05-20
