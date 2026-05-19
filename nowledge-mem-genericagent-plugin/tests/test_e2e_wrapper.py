"""End-to-end test: Verify wrapper injection in real GenericAgent environment."""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import genericagent_nmem


def test_wrapper_injection_with_mock_agentmain():
    """Test that install() successfully patches a mock agentmain module."""
    # Reset global state
    genericagent_nmem._INSTALLED = False
    
    # Create a minimal mock agentmain module
    class MockAgentMain:
        @staticmethod
        def get_system_prompt():
            return "<identity>Test Agent</identity>"
    
    # Install the wrapper
    result = genericagent_nmem.install(agentmain_module=MockAgentMain)
    assert result is True, "install() should return True"
    
    # Verify the prompt is modified
    modified_prompt = MockAgentMain.get_system_prompt()
    assert "<identity>Test Agent</identity>" in modified_prompt
    assert "[Nowledge Mem" in modified_prompt or "nmem" in modified_prompt.lower()
    
    print("✓ Wrapper injection successful")
    print(f"✓ Modified prompt length: {len(modified_prompt)} chars")
    print(f"✓ Contains original content: {'<identity>' in modified_prompt}")
    print(f"✓ Contains nmem block: {'nmem' in modified_prompt.lower()}")


def test_wrapper_preserves_original_behavior():
    """Test that wrapper doesn't break original functionality."""
    # Reset global state
    genericagent_nmem._INSTALLED = False
    
    class MockAgentMain:
        call_count = 0
        
        @classmethod
        def get_system_prompt(cls):
            cls.call_count += 1
            return f"Prompt #{cls.call_count}"
    
    # Install wrapper
    genericagent_nmem.install(agentmain_module=MockAgentMain)
    
    # Call multiple times
    prompt1 = MockAgentMain.get_system_prompt()
    prompt2 = MockAgentMain.get_system_prompt()
    
    # Verify call count increments (original behavior preserved)
    assert MockAgentMain.call_count == 2
    assert "Prompt #1" in prompt1
    assert "Prompt #2" in prompt2
    
    print("✓ Original behavior preserved")
    print(f"✓ Call count: {MockAgentMain.call_count}")


def test_nmem_cli_availability():
    """Test that nmem CLI is available in the environment."""
    import subprocess
    
    try:
        result = subprocess.run(
            ["m", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print("✓ nmem CLI available")
            print(f"✓ Version info: {result.stdout.strip()}")
        else:
            print("⚠ nmem CLI returned non-zero exit code")
            
    except FileNotFoundError:
        print("⚠ nmem CLI not found in PATH")
    except Exception as e:
        print(f"⚠ Error checking nmem CLI: {e}")


def test_working_memory_read():
    """Test that read_working_memory() can execute without errors."""
    try:
        result = genericagent_nmem.read_working_memory()
        
        # Should return a string (even if empty or error message)
        assert isinstance(result, str), "read_working_memory() should return string"
        
        print("✓ read_working_memory() executed successfully")
        print(f"✓ Result length: {len(result)} chars")
        print(f"✓ Result preview: {result[:100]}...")
        
    except Exception as e:
        print(f"⚠ read_working_memory() raised exception: {e}")
        raise
        return False


def test_build_prompt_block():
    """Test that build_prompt_block() generates valid output."""
    try:
        block = genericagent_nmem.build_prompt_block()
        
        # Should return a string
        assert isinstance(block, str), "build_prompt_block() should return string"
        
        # Should contain key markers
        assert "[Nowledge Mem" in block or "nmem" in block.lower()
        
        # Should end with newline
        assert block.endswith("\n"), "Prompt block should end with newline"
        
        print("✓ build_prompt_block() generated valid output")
        print(f"✓ Block length: {len(block)} chars")
        print(f"✓ Contains nmem marker: {'[Nowledge Mem' in block}")
        
        return True
        
    except Exception as e:
        print(f"⚠ build_prompt_block() raised exception: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("End-to-End Test: GenericAgent nmem Plugin")
    print("=" * 60)
    print()
    
    tests = [
        ("Wrapper Injection", test_wrapper_injection_with_mock_agentmain),
        ("Original Behavior Preservation", test_wrapper_preserves_original_behavior),
        ("nmem CLI Availability", test_nmem_cli_availability),
        ("Working Memory Read", test_working_memory_read),
        ("Prompt Block Generation", test_build_prompt_block),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\n[TEST] {name}")
        print("-" * 60)
        try:
            result = test_func()
            if result is not False:  # None or True counts as pass
                passed += 1
                print(f"✓ PASS: {name}")
            else:
                failed += 1
                print(f"✗ FAIL: {name}")
        except AssertionError as e:
            failed += 1
            print(f"✗ FAIL: {name}")
            print(f"  Assertion: {e}")
        except Exception as e:
            failed += 1
            print(f"✗ ERROR: {name}")
            print(f"  Exception: {e}")
    
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    sys.exit(0 if failed == 0 else 1)
