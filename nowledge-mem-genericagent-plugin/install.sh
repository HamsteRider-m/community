#!/bin/bash
# Nowledge Mem for GenericAgent - Installation Script
# Version: 0.1.0
# Usage: ./install.sh [GENERICAGENT_ROOT]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default GenericAgent root
GA_ROOT="${1:-$HOME/Projects/GenericAgent}"

echo "============================================================"
echo "Nowledge Mem for GenericAgent - Installation"
echo "============================================================"
echo ""

# Validate GenericAgent root
if [ ! -d "$GA_ROOT" ]; then
    echo -e "${RED}✗ GenericAgent root not found: $GA_ROOT${NC}"
    echo "Usage: ./install.sh /path/to/GenericAgent"
    exit 1
fi

echo -e "${GREEN}✓ GenericAgent root found: $GA_ROOT${NC}"

# Check if nmem is available
if ! command -v nmem &> /dev/null; then
    echo -e "${YELLOW}⚠ nmem command not found. Install with: pip install nmem-cli${NC}"
    echo "  Continuing installation anyway..."
else
    echo -e "${GREEN}✓ nmem CLI found: $(which nmem)${NC}"
fi

# Create directories
echo ""
echo "Creating directories..."
mkdir -p "$GA_ROOT/memory"
mkdir -p "$GA_ROOT/.omx/ga_nmem_hook"
echo -e "${GREEN}✓ Directories created${NC}"

# Copy scripts
echo ""
echo "Installing scripts..."
SCRIPT_COUNT=0
for script in scripts/*.py; do
    if [ -f "$script" ]; then
        cp "$script" "$GA_ROOT/memory/"
        chmod +x "$GA_ROOT/memory/$(basename $script)"
        echo "  ✓ $(basename $script)"
        ((SCRIPT_COUNT++))
    fi
done
echo -e "${GREEN}✓ $SCRIPT_COUNT scripts installed${NC}"

# Copy hooks
echo ""
echo "Installing hooks..."
HOOK_COUNT=0
for hook in hooks/*.py; do
    if [ -f "$hook" ]; then
        cp "$hook" "$GA_ROOT/.omx/ga_nmem_hook/"
        chmod +x "$GA_ROOT/.omx/ga_nmem_hook/$(basename $hook)"
        echo "  ✓ $(basename $hook)"
        ((HOOK_COUNT++))
    fi
done
echo -e "${GREEN}✓ $HOOK_COUNT hooks installed${NC}"

# Copy documentation
echo ""
echo "Installing documentation..."
cp README.md "$GA_ROOT/memory/nmem_integration_README.md"
cp CHANGELOG.md "$GA_ROOT/memory/nmem_integration_CHANGELOG.md"
cp MIGRATION.md "$GA_ROOT/memory/nmem_integration_MIGRATION.md"
echo -e "${GREEN}✓ Documentation installed${NC}"

# Run tests
echo ""
echo "============================================================"
echo "Running Integration Tests"
echo "============================================================"
echo ""

cd "$GA_ROOT/memory"
if python3 test_nmem_integration.py; then
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}✓ Installation Complete!${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Verify: nmem status"
    echo "  2. Test: cd $GA_ROOT/memory && python3 nmem_layered_read.py index -n 5"
    echo "  3. Configure: export NMEM_SPACE=\"genericagent-default\""
    echo ""
    echo "Documentation:"
    echo "  - README: $GA_ROOT/memory/nmem_integration_README.md"
    echo "  - Migration Guide: $GA_ROOT/memory/nmem_integration_MIGRATION.md"
    echo "  - Changelog: $GA_ROOT/memory/nmem_integration_CHANGELOG.md"
    echo ""
else
    echo ""
    echo -e "${YELLOW}============================================================${NC}"
    echo -e "${YELLOW}⚠ Installation complete but tests failed${NC}"
    echo -e "${YELLOW}============================================================${NC}"
    echo ""
    echo "Files installed successfully, but integration tests failed."
    echo "This may be due to:"
    echo "  - nmem not running (check: nmem status)"
    echo "  - Missing dependencies (check: pip list | grep nmem)"
    echo "  - Network issues"
    echo ""
    echo "See MIGRATION.md for troubleshooting steps."
    echo ""
    exit 1
fi
