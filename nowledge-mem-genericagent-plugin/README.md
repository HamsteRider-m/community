# Nowledge Mem for GenericAgent

Personal knowledge graph integration for [GenericAgent](https://github.com/lsdefine/GenericAgent) with layered read, entity tracking, space management, auto-recall, and session sync.

## ⚠️ GenericAgent-Specific Implementation

**This plugin uses GenericAgent's Python code injection mechanism, not JSON configuration hooks.**

Unlike other plugins in this repository (e.g., Droid, Copilot CLI) that use `hooks.json`:
- ❌ **Does NOT use** `hooks.json` (GenericAgent doesn't support JSON hook configs)
- ✅ **Uses** Python `install()` method in `.omx/ga_nmem_hook/run_agentmain.py`

**Hook mechanism**:
```python
# .omx/ga_nmem_hook/run_agentmain.py
import nmem_session_sync
nmem_session_sync.install(agentmain.GeneraticAgent)  # Direct class injection
```

For details, see [hooks/README.md](hooks/README.md).

**Reference**: [GenericAgent Documentation](https://datawhalechina.github.io/hello-generic-agent/)

## Features

### Phase 1: Core MVP
- **Layered Read** (`nmem_layered_read.py`) - Avoid context pollution with 4 read modes:
  - `index` - Lightweight thread list (id/title/metadata only)
  - `search` - Query with snippets
  - `page` - Full thread content
  - `export` - Bulk export for analysis
- **Working Memory** - Read current priorities via `nmem wm`
- **Thread Management** - Create and search threads
- **Space Support** - Multi-project context isolation via `NMEM_SPACE`

### Phase 2: Enhancements
- **Entity Tracking** (`nmem_entity_tracker.py`) - Track entities across memories:
  - `search <entity>` - Find all mentions
  - `expand <memory_id>` - Get related memories
  - `evolves <entity>` - Track entity evolution over time
- **Space Management** (`nmem_space_manager.py`) - Full space lifecycle:
  - `list` - Show all spaces
  - `current` - Display active space
  - `create` - Provision new space
  - `update` - Modify space config

### Phase 3: Advanced
- **Auto-recall** (`nmem_auto_recall.py`) - Automatic memory retrieval based on context
- **Session Sync** (`nmem_session_sync.py`) - Automatic session capture and handoff

## Installation

### Prerequisites

1. **Nowledge Mem** must be running:
   ```bash
   nmem status
   ```
   If not installed, get it from [mem.nowledge.co](https://mem.nowledge.co)

2. **GenericAgent** must be installed and configured

### Plugin Installation

```bash
# Clone the community repo
git clone https://github.com/nowledge-co/community.git
cd community

# Copy plugin to GenericAgent memory directory
cp -r nowledge-mem-genericagent-plugin/scripts/* /path/to/GenericAgent/memory/
cp -r nowledge-mem-genericagent-plugin/hooks/* /path/to/GenericAgent/.omx/ga_nmem_hook/

# Make scripts executable
chmod +x /path/to/GenericAgent/memory/nmem_*.py
chmod +x /path/to/GenericAgent/.omx/ga_nmem_hook/*.py
```

### Verification

Run the integration test suite:

```bash
cd /path/to/GenericAgent/memory
python3 test_nmem_integration.py
```

Expected output: `9/9 tests passed (100.0%)`

## Usage

### Basic Commands

```bash
# Read Working Memory
nmem wm

# Layered read - index only
python3 nmem_layered_read.py index -n 10

# Search with context
python3 nmem_layered_read.py search "GenericAgent" -n 5

# Track entity
python3 nmem_entity_tracker.py search "project-name"

# Manage spaces
python3 nmem_space_manager.py list
export NMEM_SPACE="my-project"
```

### Integration with GenericAgent

The plugin integrates with GenericAgent's memory system:

1. **Startup**: Auto-reads Working Memory if configured
2. **During execution**: Uses layered read to avoid context pollution
3. **Entity tracking**: Maintains entity relationships across sessions
4. **Space isolation**: Keeps project contexts separate
5. **Session sync**: Automatically captures important sessions

### Configuration

Set environment variables in your GenericAgent config:

```bash
# Optional: Set default space
export NMEM_SPACE="genericagent-default"

# Optional: API configuration (if not using default)
export NMEM_API_URL="http://localhost:8080"
export NMEM_API_KEY="your-key-here"
```

## Architecture

### Transport Layer
- **Primary**: `nmem` CLI (universal fallback)
- **Fallback**: `uvx --from nmem-cli nmem` (auto-download)
- **Future**: MCP support when GenericAgent adds MCP runtime

### File Structure
```
nowledge-mem-genericagent-plugin/
├── scripts/
│   ├── nmem_layered_read.py      # Phase 1: Core layered read
│   ├── nmem_entity_tracker.py    # Phase 2: Entity tracking
│   ├── nmem_space_manager.py     # Phase 2: Space management
│   ├── nmem_auto_recall.py       # Phase 3: Auto-recall
│   └── test_nmem_integration.py  # Integration tests
├── hooks/
│   └── nmem_session_sync.py      # Phase 3: Session capture
├── .factory-plugin/
│   └── plugin.json               # Plugin metadata
└── README.md                     # This file
```

## Protocol

All tools follow the `nmem-layered-v1` protocol:
- **Minimal context**: Only load what's needed
- **Explicit retrieval**: No automatic full-context injection
- **Space-aware**: Respect ambient space context
- **CLI-first**: Use `nmem` commands as foundation

## Testing

The plugin includes a comprehensive test suite covering all phases:

```bash
python3 scripts/test_nmem_integration.py
```

Tests verify:
- Phase 1: index, search, working memory, thread creation
- Phase 2: entity tracking, space management
- Phase 3: auto-recall, session sync

## Behavioral Guidance

This plugin follows [Nowledge Mem Behavioral Guidance](https://github.com/nowledge-co/community/blob/main/shared/behavioral-guidance.md):

1. **Working Memory**: Read once at session start
2. **Proactive Search**: Search when past insights would help
3. **Distillation**: Save stable conclusions as durable memories
4. **Handoff**: Create resumable summaries for context transfer
5. **Space Awareness**: Respect ambient project context

## Troubleshooting

### nmem command not found
```bash
# Check if nmem is installed
which nmem

# If not, install via pip
pip install nmem-cli

# Or use uvx fallback
uvx --from nmem-cli nmem status
```

### Tests failing
```bash
# Verify nmem is running
nmem status

# Check API connectivity
nmem -j wm read

# Re-run with verbose output
python3 test_nmem_integration.py 2>&1 | tee test.log
```

### Space not switching
```bash
# Verify space exists
nmem spaces list

# Create if needed
nmem spaces create "my-project"

# Set environment variable
export NMEM_SPACE="my-project"
nmem wm read  # Should show space in output
```

## Contributing

This plugin is part of the [Nowledge Community](https://github.com/nowledge-co/community). 

To contribute:
1. Test thoroughly with GenericAgent
2. Ensure all integration tests pass
3. Follow the [Plugin Development Guide](https://github.com/nowledge-co/community/blob/main/docs/PLUGIN_DEVELOPMENT_GUIDE.md)
4. Submit PR with clear description of changes

## Version History

- **0.1.0** (2026-05-19)
  - Initial release
  - Phase 1-3 complete (9/9 tests passing)
  - Layered read, entity tracking, space management
  - Auto-recall and session sync

## License

MIT License - See [LICENSE](../../LICENSE) for details

## Links

- [Nowledge Mem](https://mem.nowledge.co)
- [GenericAgent](https://github.com/yourusername/GenericAgent)
- [Community Integrations](https://github.com/nowledge-co/community)
- [Documentation](https://mem.nowledge.co/docs)
