# GenericAgent Integration Migration Guide

This guide ensures complete and lossless migration of the Nowledge Mem integration to GenericAgent.

## Prerequisites

- GenericAgent installed and configured
- Nowledge Mem running (`nmem status`)
- Python 3.7+ available
- Git access to nowledge-co/community repository

## Migration Checklist

### 1. Clone Community Repository

```bash
cd ~/Projects  # or your preferred location
git clone https://github.com/nowledge-co/community.git nowledge-community
cd nowledge-community
git checkout feature/genericagent-integration
```

### 2. Verify Plugin Files

Ensure all files are present in `nowledge-mem-genericagent-plugin/`:

```bash
cd nowledge-mem-genericagent-plugin

# Check directory structure
ls -la

# Expected structure:
# ├── .factory-plugin/
# │   └── plugin.json
# ├── hooks/
# │   └── nmem_session_sync.py
# ├── scripts/
# │   ├── nmem_layered_read.py
# │   ├── nmem_entity_tracker.py
# │   ├── nmem_space_manager.py
# │   ├── nmem_auto_recall.py
# │   └── test_nmem_integration.py
# ├── CHANGELOG.md
# ├── MIGRATION.md (this file)
# └── README.md
```

### 3. Install to GenericAgent

**Option A: Automated Installation (Recommended)**

```bash
# Run the installation script
./install.sh /path/to/GenericAgent
```

**Option B: Manual Installation**

```bash
# Set GenericAgent path
GA_ROOT="/path/to/GenericAgent"

# Copy scripts to memory directory
cp scripts/*.py "$GA_ROOT/memory/"

# Copy hooks to .omx directory
mkdir -p "$GA_ROOT/.omx/ga_nmem_hook"
cp hooks/*.py "$GA_ROOT/.omx/ga_nmem_hook/"

# Set executable permissions
chmod +x "$GA_ROOT/memory/nmem_"*.py
chmod +x "$GA_ROOT/.omx/ga_nmem_hook/"*.py

# Copy documentation (optional but recommended)
cp README.md "$GA_ROOT/memory/nmem_integration_README.md"
cp CHANGELOG.md "$GA_ROOT/memory/nmem_integration_CHANGELOG.md"
```

### 4. Verify Installation

```bash
cd /path/to/GenericAgent/memory

# Run integration tests
python3 test_nmem_integration.py

# Expected output:
# ============================================================
# GenericAgent × nmem Integration Test Suite
# ============================================================
# 
# Phase 1: ✅ PASS (4/4)
# Phase 2: ✅ PASS (3/3)
# Phase 3: ✅ PASS (2/2)
# 
# ============================================================
# OVERALL: 9/9 tests passed (100.0%)
# ============================================================
```

### 5. Configure Environment (Optional)

Add to your GenericAgent configuration or shell profile:

```bash
# Set default space for GenericAgent
export NMEM_SPACE="genericagent-default"

# Optional: Custom API endpoint
# export NMEM_API_URL="http://localhost:8080"
# export NMEM_API_KEY="your-key-here"
```

### 6. Test Basic Functionality

```bash
# Test Working Memory access
nmem wm read

# Test layered read
python3 nmem_layered_read.py index -n 5

# Test entity tracking
python3 nmem_entity_tracker.py search "test"

# Test space management
python3 nmem_space_manager.py list
```

## Verification Checklist

- [ ] All 5 script files copied to `memory/`
- [ ] Hook file copied to `.omx/ga_nmem_hook/`
- [ ] All files have executable permissions
- [ ] Integration test suite passes (9/9 tests)
- [ ] `nmem wm read` works
- [ ] Layered read tools work
- [ ] Entity tracker works
- [ ] Space manager works
- [ ] Documentation copied (optional)

## Troubleshooting

### Tests Failing

**Issue**: `nmem: command not found`

```bash
# Check if nmem is installed
which nmem

# If not, install via pip
pip install nmem-cli

# Or use uvx fallback
uvx --from nmem-cli nmem status
```

**Issue**: `ModuleNotFoundError: No module named 'X'`

```bash
# Install required dependencies
pip install requests  # if needed
```

**Issue**: Tests pass but tools don't work in GenericAgent

```bash
# Verify Python path
which python3

# Check if scripts are in PATH
echo $PYTHONPATH

# Ensure GenericAgent can find the scripts
cd /path/to/GenericAgent/memory
python3 -c "import nmem_layered_read; print('OK')"
```

### Permission Issues

```bash
# Fix permissions
chmod +x /path/to/GenericAgent/memory/nmem_*.py
chmod +x /path/to/GenericAgent/.omx/ga_nmem_hook/*.py
```

### Space Not Switching

```bash
# Verify space exists
nmem spaces list

# Create if needed
nmem spaces create "genericagent-default"

# Set environment variable
export NMEM_SPACE="genericagent-default"

# Verify
nmem wm read  # Should show space in output
```

## Rollback

If you need to rollback the installation:

```bash
# Remove installed files
rm /path/to/GenericAgent/memory/nmem_*.py
rm /path/to/GenericAgent/memory/test_nmem_integration.py
rm -rf /path/to/GenericAgent/.omx/ga_nmem_hook/nmem_session_sync.py

# Remove documentation (if copied)
rm /path/to/GenericAgent/memory/nmem_integration_*.md
```

## Updating

To update to a newer version:

```bash
# Pull latest changes
cd ~/Projects/nowledge-community
git pull origin feature/genericagent-integration

# Re-run installation
cd nowledge-mem-genericagent-plugin
./install.sh /path/to/GenericAgent

# Verify
cd /path/to/GenericAgent/memory
python3 test_nmem_integration.py
```

## Integration with GenericAgent Workflows

### Startup Hook

Add to GenericAgent startup script:

```python
# Auto-read Working Memory on startup
import subprocess
result = subprocess.run(['nmem', 'wm', 'read'], capture_output=True, text=True)
if result.returncode == 0:
    print("Working Memory loaded")
```

### Session End Hook

Add to GenericAgent session end:

```python
# Auto-save session summary
from nmem_session_sync import NmemSessionSync
sync = NmemSessionSync()
sync.capture_session(session_data)
```

### Entity Tracking Hook

Add to GenericAgent entity detection:

```python
# Track important entities
from nmem_entity_tracker import track_entity
track_entity("project-name", context)
```

## Support

- **Documentation**: [FILE:/Users/maygo/Projects/nowledge-community/nowledge-mem-genericagent-plugin/README.md]
- **Issues**: https://github.com/nowledge-co/community/issues
- **Community**: https://discord.gg/nowledge

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for version history and updates.

---

**Last Updated**: 2026-05-19  
**Version**: 0.1.0  
**Status**: Ready for testing
