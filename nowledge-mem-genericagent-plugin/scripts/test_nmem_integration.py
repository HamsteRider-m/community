#!/usr/bin/env python3
"""
Comprehensive integration test suite for GenericAgent × nmem.

Tests all Phase 1-3 capabilities with actual execution.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path


# Test configuration
MEMORY_DIR = Path(__file__).parent
TEST_SPACE = "test-integration"
TEST_RESULTS = []


def run_command(cmd, timeout=10):
    """Run a command and return result."""
    try:
        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            shell=isinstance(cmd, str)
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Timeout",
            "stdout": "",
            "stderr": "Command timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e)
        }


def test_phase1_layered_read():
    """Test Phase 1: Layered Read capabilities."""
    print("\n=== Phase 1: Layered Read ===")
    tests = []
    
    # Test 1: Index
    print("  [1/4] Testing index...")
    result = run_command([
        "python3", str(MEMORY_DIR / "nmem_layered_read.py"),
        "index", "-n", "3"
    ])
    if result["success"]:
        try:
            data = json.loads(result["stdout"])
            tests.append({
                "name": "index",
                "passed": data.get("protocol") == "nmem-layered-v1/index",
                "details": f"Returned {len(data.get('threads', []))} threads"
            })
        except json.JSONDecodeError:
            tests.append({"name": "index", "passed": False, "details": "Invalid JSON"})
    else:
        tests.append({"name": "index", "passed": False, "details": result.get("stderr", "")})
    
    # Test 2: Search
    print("  [2/4] Testing search...")
    result = run_command([
        "python3", str(MEMORY_DIR / "nmem_layered_read.py"),
        "search", "test", "-n", "2"
    ])
    if result["success"]:
        try:
            data = json.loads(result["stdout"])
            tests.append({
                "name": "search",
                "passed": data.get("protocol") == "nmem-layered-v1/search",
                "details": f"Query: {data.get('query')}"
            })
        except json.JSONDecodeError:
            tests.append({"name": "search", "passed": False, "details": "Invalid JSON"})
    else:
        tests.append({"name": "search", "passed": False, "details": result.get("stderr", "")})
    
    # Test 3: Working Memory
    print("  [3/4] Testing working memory...")
    result = run_command(["nmem", "wm"])
    tests.append({
        "name": "working_memory",
        "passed": result["success"],
        "details": "CLI accessible"
    })
    
    # Test 4: Thread Creation (handoff-only)
    print("  [4/4] Testing thread creation...")
    result = run_command([
        "nmem", "-j", "t", "create",
        "-t", "Integration Test",
        "-c", "Phase 1 layered read capabilities verified",
        "-s", "genericagent-test"
    ])
    if result["success"]:
        try:
            data = json.loads(result["stdout"])
            tests.append({
                "name": "thread_create",
                "passed": "id" in data,
                "details": f"Created thread: {data.get('id', 'N/A')}"
            })
        except json.JSONDecodeError:
            tests.append({"name": "thread_create", "passed": False, "details": "Invalid JSON"})
    else:
        tests.append({"name": "thread_create", "passed": False, "details": result.get("stderr", "")})
    
    return tests


def test_phase2_enhancements():
    """Test Phase 2: Enhanced capabilities."""
    print("\n=== Phase 2: Enhancements ===")
    tests = []
    
    # Test 1: Entity Tracking
    print("  [1/3] Testing entity tracker...")
    result = run_command([
        "python3", str(MEMORY_DIR / "nmem_entity_tracker.py"),
        "search", "GenericAgent", "-n", "3"
    ])
    if result["success"]:
        try:
            data = json.loads(result["stdout"])
            tests.append({
                "name": "entity_tracker",
                "passed": data.get("protocol") == "nmem-entity-v1/search",
                "details": f"Found {data.get('total', 0)} mentions"
            })
        except json.JSONDecodeError:
            tests.append({"name": "entity_tracker", "passed": False, "details": "Invalid JSON"})
    else:
        tests.append({"name": "entity_tracker", "passed": False, "details": result.get("stderr", "")})
    
    # Test 2: Space Manager - List
    print("  [2/3] Testing space manager...")
    result = run_command([
        "python3", str(MEMORY_DIR / "nmem_space_manager.py"),
        "list"
    ])
    if result["success"]:
        try:
            data = json.loads(result["stdout"])
            tests.append({
                "name": "space_manager_list",
                "passed": data.get("protocol") == "nmem-space-v1/list",
                "details": f"{len(data.get('spaces', []))} spaces available"
            })
        except json.JSONDecodeError:
            tests.append({"name": "space_manager_list", "passed": False, "details": "Invalid JSON"})
    else:
        tests.append({"name": "space_manager_list", "passed": False, "details": result.get("stderr", "")})
    
    # Test 3: Space Manager - Current
    print("  [3/3] Testing current space...")
    result = run_command([
        "python3", str(MEMORY_DIR / "nmem_space_manager.py"),
        "current"
    ])
    if result["success"]:
        try:
            data = json.loads(result["stdout"])
            tests.append({
                "name": "space_manager_current",
                "passed": data.get("protocol") == "nmem-space-v1/current",
                "details": f"Current: {data.get('space')}"
            })
        except json.JSONDecodeError:
            tests.append({"name": "space_manager_current", "passed": False, "details": "Invalid JSON"})
    else:
        tests.append({"name": "space_manager_current", "passed": False, "details": result.get("stderr", "")})
    
    return tests


def test_phase3_advanced():
    """Test Phase 3: Advanced capabilities."""
    print("\n=== Phase 3: Advanced ===")
    tests = []
    
    # Test 1: Auto-recall
    print("  [1/2] Testing auto-recall...")
    result = run_command([
        "python3", str(MEMORY_DIR / "nmem_auto_recall.py"),
        "test query", "-n", "2"
    ])
    if result["success"]:
        try:
            data = json.loads(result["stdout"])
            tests.append({
                "name": "auto_recall",
                "passed": data.get("protocol") == "nmem-auto-recall-v1/test",
                "details": f"Memories found: {data.get('memories_found', 0)}"
            })
        except json.JSONDecodeError:
            tests.append({"name": "auto_recall", "passed": False, "details": "Invalid JSON"})
    else:
        tests.append({"name": "auto_recall", "passed": False, "details": result.get("stderr", "")})
    
    # Test 2: Session Sync (check if module exists)
    print("  [2/2] Testing session sync...")
    session_sync_path = Path(__file__).parent.parent / ".omx" / "ga_nmem_hook" / "nmem_session_sync.py"
    if session_sync_path.exists():
        result = run_command([
            "python3", "-c",
            f"import sys; sys.path.insert(0, '{session_sync_path.parent}'); import nmem_session_sync; print('OK')"
        ])
        tests.append({
            "name": "session_sync",
            "passed": result["success"] and "OK" in result["stdout"],
            "details": "Module importable"
        })
    else:
        tests.append({
            "name": "session_sync",
            "passed": False,
            "details": "Module not found"
        })
    
    return tests


def print_summary(all_tests):
    """Print test summary."""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    phase_results = {
        "Phase 1": all_tests[:4],
        "Phase 2": all_tests[4:7],
        "Phase 3": all_tests[7:]
    }
    
    for phase, tests in phase_results.items():
        passed = sum(1 for t in tests if t["passed"])
        total = len(tests)
        status = "✅ PASS" if passed == total else f"⚠️  {passed}/{total}"
        print(f"\n{phase}: {status}")
        for test in tests:
            icon = "✅" if test["passed"] else "❌"
            print(f"  {icon} {test['name']}: {test['details']}")
    
    total_passed = sum(1 for t in all_tests if t["passed"])
    total_tests = len(all_tests)
    percentage = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"OVERALL: {total_passed}/{total_tests} tests passed ({percentage:.1f}%)")
    print(f"{'='*60}\n")
    
    return total_passed == total_tests


def main():
    print("GenericAgent × nmem Integration Test Suite")
    print("="*60)
    
    all_tests = []
    all_tests.extend(test_phase1_layered_read())
    all_tests.extend(test_phase2_enhancements())
    all_tests.extend(test_phase3_advanced())
    
    success = print_summary(all_tests)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
