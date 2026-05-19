"""Tests for install() function and monkey patching in genericagent_nmem."""
import sys
import os
from unittest.mock import patch, MagicMock, call
import pytest

# Add parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import genericagent_nmem


class TestInstall:
    """Test install() function and monkey patching."""

    def test_install_without_agentmain_module(self):
        """Test install() when agentmain module is not provided and import fails."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        # The source code uses `import agentmain` which cannot be easily mocked
        # We test the behavior by passing None and ensuring agentmain doesn't exist
        import sys
        agentmain_backup = sys.modules.pop('agentmain', None)
        
        try:
            # Call install with None, should try to import agentmain and fail
            result = genericagent_nmem.install(agentmain_module=None)
            # If agentmain doesn't exist, install should return False
            assert result is False
        finally:
            # Restore agentmain if it was there
            if agentmain_backup is not None:
                sys.modules['agentmain'] = agentmain_backup

    def test_install_module_without_get_system_prompt(self):
        """Test install() when module doesn't have get_system_prompt."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        # Create a module without get_system_prompt attribute
        mock_module = type('MockModule', (), {})()
        
        result = genericagent_nmem.install(agentmain_module=mock_module)
        assert result is False

    def test_install_module_with_non_callable_get_system_prompt(self):
        """Test install() when get_system_prompt is not callable."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        # Create a module with non-callable get_system_prompt
        mock_module = type('MockModule', (), {'get_system_prompt': "not a function"})()
        
        result = genericagent_nmem.install(agentmain_module=mock_module)
        assert result is False

    def test_install_success_with_valid_module(self):
        """Test successful installation with valid agentmain module."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        # Create a mock module with get_system_prompt
        mock_module = MagicMock()
        original_get_system_prompt = MagicMock(return_value="original prompt")
        mock_module.get_system_prompt = original_get_system_prompt
        
        # Mock build_prompt_block to return a known value
        with patch('genericagent_nmem.build_prompt_block', return_value="[nmem block]\n"):
            result = genericagent_nmem.install(agentmain_module=mock_module)
            
            assert result is True
            # Verify that get_system_prompt was replaced
            assert mock_module.get_system_prompt != original_get_system_prompt
            # Verify global flag
            assert genericagent_nmem._INSTALLED is True

    def test_install_preserves_original_prompt(self):
        """Test that install() preserves the original system prompt."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        mock_module = MagicMock()
        original_prompt = "This is the original system prompt"
        mock_module.get_system_prompt = MagicMock(return_value=original_prompt)
        
        with patch('genericagent_nmem.build_prompt_block', return_value="[nmem]\n"):
            genericagent_nmem.install(agentmain_module=mock_module)
            
            # Call the wrapped function
            result = mock_module.get_system_prompt()
            
            # Should contain both original prompt and nmem block
            assert original_prompt in result
            assert "[nmem]" in result

    def test_install_appends_nmem_block(self):
        """Test that nmem block is appended to original prompt (not prepended)."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        mock_module = MagicMock()
        original_prompt = "Original prompt content"
        mock_module.get_system_prompt = MagicMock(return_value=original_prompt)
        
        nmem_block = "[Nowledge Mem Integration]\nTest content\n"
        with patch('genericagent_nmem.build_prompt_block', return_value=nmem_block):
            genericagent_nmem.install(agentmain_module=mock_module)
            
            result = mock_module.get_system_prompt()
            
            # Original prompt should come before nmem block (appended)
            original_index = result.find(original_prompt)
            nmem_index = result.find(nmem_block)
            assert original_index < nmem_index
            # Verify exact structure: original + nmem
            assert result == original_prompt + nmem_block

    def test_install_handles_empty_nmem_block(self):
        """Test behavior when nmem block is empty."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        mock_module = MagicMock()
        original_prompt = "Original prompt"
        mock_module.get_system_prompt = MagicMock(return_value=original_prompt)
        
        with patch('genericagent_nmem.build_prompt_block', return_value=""):
            genericagent_nmem.install(agentmain_module=mock_module)
            
            result = mock_module.get_system_prompt()
            # Should be original + empty string
            assert result == original_prompt

    def test_install_handles_multiline_prompts(self):
        """Test that install() correctly handles multiline prompts."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        mock_module = MagicMock()
        original_prompt = "Line 1\nLine 2\nLine 3"
        mock_module.get_system_prompt = MagicMock(return_value=original_prompt)
        
        nmem_block = "[nmem]\nBlock line 1\nBlock line 2\n"
        with patch('genericagent_nmem.build_prompt_block', return_value=nmem_block):
            genericagent_nmem.install(agentmain_module=mock_module)
            
            result = mock_module.get_system_prompt()
            
            # Check structure: original + nmem
            assert result == original_prompt + nmem_block
            # Count newlines to verify structure
            assert result.count('\n') == original_prompt.count('\n') + nmem_block.count('\n')

    def test_install_idempotency(self):
        """Test that calling install() when already installed returns True."""
        # Reset and install once
        genericagent_nmem._INSTALLED = False
        
        mock_module = MagicMock()
        original_prompt = "Original"
        mock_module.get_system_prompt = MagicMock(return_value=original_prompt)
        
        with patch('genericagent_nmem.build_prompt_block', return_value="[nmem]\n"):
            # First install
            result1 = genericagent_nmem.install(agentmain_module=mock_module)
            assert result1 is True
            assert genericagent_nmem._INSTALLED is True
            
            # Second install should return True immediately without patching
            result2 = genericagent_nmem.install(agentmain_module=mock_module)
            assert result2 is True

    def test_install_with_exception_in_original_function(self):
        """Test that wrapper propagates exceptions from original function."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        mock_module = MagicMock()
        
        def failing_func():
            raise ValueError("Original function failed")
        
        mock_module.get_system_prompt = failing_func
        
        with patch('genericagent_nmem.build_prompt_block', return_value="[nmem]\n"):
            genericagent_nmem.install(agentmain_module=mock_module)
            
            # Should propagate the exception
            with pytest.raises(ValueError, match="Original function failed"):
                mock_module.get_system_prompt()

    def test_install_with_exception_in_build_prompt_block(self):
        """Test behavior when build_prompt_block raises exception."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        mock_module = MagicMock()
        mock_module.get_system_prompt = MagicMock(return_value="Original")
        
        with patch('genericagent_nmem.build_prompt_block', side_effect=RuntimeError("nmem error")):
            genericagent_nmem.install(agentmain_module=mock_module)
            
            # Should propagate the exception when calling wrapped function
            with pytest.raises(RuntimeError, match="nmem error"):
                mock_module.get_system_prompt()

    def test_install_wrapped_function_is_callable(self):
        """Test that wrapped function is still callable."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        mock_module = MagicMock()
        
        def original_with_docstring():
            """This is the original docstring."""
            return "prompt"
        
        mock_module.get_system_prompt = original_with_docstring
        
        with patch('genericagent_nmem.build_prompt_block', return_value="[nmem]\n"):
            genericagent_nmem.install(agentmain_module=mock_module)
            
            # Wrapped function should still be callable
            assert callable(mock_module.get_system_prompt)
            result = mock_module.get_system_prompt()
            assert "prompt" in result
            assert "[nmem]" in result


class TestInstallIntegration:
    """Integration tests for install() with realistic scenarios."""

    def test_install_with_realistic_agentmain_structure(self):
        """Test install() with a structure similar to real agentmain."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        # Create a mock that simulates agentmain module structure
        mock_agentmain = MagicMock()
        
        def realistic_get_system_prompt():
            return """<identity>
You are Kiro, an AI assistant.
</identity>

<capabilities>
- Code execution
- File operations
</capabilities>"""
        
        mock_agentmain.get_system_prompt = realistic_get_system_prompt
        
        realistic_nmem_block = """

[Nowledge Mem / nmem integration for GenericAgent]

Integration status: working-memory-loaded

[Nowledge Working Memory]
Test working memory content
"""
        
        with patch('genericagent_nmem.build_prompt_block', return_value=realistic_nmem_block):
            result = genericagent_nmem.install(agentmain_module=mock_agentmain)
            
            assert result is True
            
            final_prompt = mock_agentmain.get_system_prompt()
            
            # Verify structure: original + nmem
            assert "<identity>" in final_prompt
            assert "Test working memory content" in final_prompt
            
            # Verify order: original comes first
            identity_pos = final_prompt.find("<identity>")
            nmem_pos = final_prompt.find("[Nowledge Mem")
            assert identity_pos < nmem_pos

    def test_install_with_empty_original_prompt(self):
        """Test install() when original prompt is empty."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        mock_module = MagicMock()
        mock_module.get_system_prompt = MagicMock(return_value="")
        
        with patch('genericagent_nmem.build_prompt_block', return_value="[nmem only]\n"):
            genericagent_nmem.install(agentmain_module=mock_module)
            
            result = mock_module.get_system_prompt()
            assert result == "[nmem only]\n"

    def test_install_with_unicode_content(self):
        """Test install() with unicode characters in prompts."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        mock_module = MagicMock()
        original_prompt = "你好世界 🌍 Привет"
        mock_module.get_system_prompt = MagicMock(return_value=original_prompt)
        
        nmem_block = "\n[nmem] 测试 🧪\n"
        with patch('genericagent_nmem.build_prompt_block', return_value=nmem_block):
            genericagent_nmem.install(agentmain_module=mock_module)
            
            result = mock_module.get_system_prompt()
            assert original_prompt in result
            assert nmem_block in result
            # Verify order
            assert result == original_prompt + nmem_block

    def test_install_global_state_management(self):
        """Test that _INSTALLED global flag works correctly."""
        # Reset global state
        genericagent_nmem._INSTALLED = False
        
        mock_module1 = MagicMock()
        mock_module1.get_system_prompt = MagicMock(return_value="prompt1")
        
        mock_module2 = MagicMock()
        mock_module2.get_system_prompt = MagicMock(return_value="prompt2")
        
        with patch('genericagent_nmem.build_prompt_block', return_value="[nmem]\n"):
            # First install
            result1 = genericagent_nmem.install(agentmain_module=mock_module1)
            assert result1 is True
            assert genericagent_nmem._INSTALLED is True
            
            # Second install with different module should return True immediately
            result2 = genericagent_nmem.install(agentmain_module=mock_module2)
            assert result2 is True
            # Second module should NOT be patched
            assert mock_module2.get_system_prompt() == "prompt2"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=genericagent_nmem", "--cov-report=term-missing"])
