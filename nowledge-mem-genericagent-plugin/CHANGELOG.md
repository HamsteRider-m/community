# Changelog

All notable changes to the Nowledge Mem GenericAgent plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-19

### Added
- Initial release of Nowledge Mem integration for GenericAgent
- **Phase 1: Core MVP**
  - Layered read tool (`nmem_layered_read.py`) with 4 modes: index, search, page, export
  - Working Memory access via `nmem wm`
  - Thread creation and search
  - Space support via `NMEM_SPACE` environment variable
- **Phase 2: Enhancements**
  - Entity tracking tool (`nmem_entity_tracker.py`) for cross-memory entity analysis
  - Space management tool (`nmem_space_manager.py`) for full space lifecycle
- **Phase 3: Advanced**
  - Auto-recall tool (`nmem_auto_recall.py`) for context-based memory retrieval
  - Session sync hook (`nmem_session_sync.py`) for automatic capture
- Comprehensive integration test suite (`test_nmem_integration.py`)
- Complete documentation (README.md, plugin.json)
- Entry in community integrations.json registry

### Testing
- 9/9 integration tests passing (100%)
- All tools verified with actual nmem CLI v0.8.6
- Protocol: `nmem-layered-v1` for minimal context pollution

### Known Limitations
- Manual installation required (no automated plugin manager yet)
- Distill functionality not implemented (nmem v0.8.6 limitation)
- MCP support pending GenericAgent MCP runtime

### Documentation
- Installation guide with verification steps
- Usage examples for all tools
- Troubleshooting section
- Architecture and protocol documentation
- Behavioral guidance alignment

[0.1.0]: https://github.com/nowledge-co/community/tree/feature/genericagent-integration/nowledge-mem-genericagent-plugin
