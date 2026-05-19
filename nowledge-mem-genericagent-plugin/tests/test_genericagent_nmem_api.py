"""Tests for genericagent_nmem module (API-based implementation)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import genericagent_nmem


class TestReadWorkingMemory:
    """Test read_working_memory function."""
    
    def test_read_working_memory_success(self):
        """Test successful working memory read."""
        mock_client = MagicMock()
        mock_client.read_working_memory.return_value = {
            "exists": True,
            "content": "Test working memory content"
        }
        
        with patch('genericagent_nmem._get_nmem_client', return_value=mock_client):
            result = genericagent_nmem.read_working_memory()
            assert result == "Test working memory content"
            mock_client.read_working_memory.assert_called_once()
    
    def test_read_working_memory_not_exists(self):
        """Test when working memory doesn't exist."""
        mock_client = MagicMock()
        mock_client.read_working_memory.return_value = {
            "exists": False
        }
        
        with patch('genericagent_nmem._get_nmem_client', return_value=mock_client):
            result = genericagent_nmem.read_working_memory()
            assert result == ""
    
    def test_read_working_memory_no_client(self):
        """Test when client is unavailable."""
        with patch('genericagent_nmem._get_nmem_client', return_value=None):
            result = genericagent_nmem.read_working_memory()
            assert result == ""
    
    def test_read_working_memory_exception(self):
        """Test when API call raises exception."""
        mock_client = MagicMock()
        mock_client.read_working_memory.side_effect = Exception("API error")
        
        with patch('genericagent_nmem._get_nmem_client', return_value=mock_client):
            result = genericagent_nmem.read_working_memory()
            assert result == ""
    
    def test_read_working_memory_max_chars(self):
        """Test max_chars truncation."""
        long_content = "x" * 10000
        mock_client = MagicMock()
        mock_client.read_working_memory.return_value = {
            "exists": True,
            "content": long_content
        }
        
        with patch('genericagent_nmem._get_nmem_client', return_value=mock_client):
            result = genericagent_nmem.read_working_memory(max_chars=100)
            assert len(result) <= 100


class TestInstall:
    """Test install function."""
    
    def test_install_success(self):
        """Test successful installation."""
        # Mock GenericAgent
        mock_ga = MagicMock()
        mock_ga.get_system_prompt = MagicMock(return_value="Original prompt")
        
        with patch.dict('sys.modules', {'generic_agent': MagicMock(GenericAgent=mock_ga)}):
            # Reset global state
            genericagent_nmem._INSTALLED = False
            
            result = genericagent_nmem.install()
            assert result is True
            assert genericagent_nmem._INSTALLED is True
    
    def test_install_already_installed(self):
        """Test installing when already installed."""
        genericagent_nmem._INSTALLED = True
        result = genericagent_nmem.install()
        assert result is True
    
    def test_install_no_generic_agent(self):
        """Test when GenericAgent is not available."""
        with patch.dict('sys.modules', {'generic_agent': None}):
            genericagent_nmem._INSTALLED = False
            result = genericagent_nmem.install()
            assert result is False


class TestPatchedGetSystemPrompt:
    """Test patched get_system_prompt behavior."""
    
    def test_patched_prompt_includes_working_memory(self):
        """Test that patched prompt includes working memory."""
        mock_ga = MagicMock()
        original_prompt = "Original system prompt"
        mock_ga.get_system_prompt = MagicMock(return_value=original_prompt)
        
        mock_client = MagicMock()
        mock_client.read_working_memory.return_value = {
            "exists": True,
            "content": "Test WM content"
        }
        
        with patch.dict('sys.modules', {'generic_agent': MagicMock(GenericAgent=mock_ga)}):
            with patch('genericagent_nmem._get_nmem_client', return_value=mock_client):
                genericagent_nmem._INSTALLED = False
                genericagent_nmem.install()
                
                # Call the patched method
                instance = mock_ga()
                result = mock_ga.get_system_prompt(instance)
                
                assert "Test WM content" in result
                assert "[Memory]" in result
    
    def test_patched_prompt_without_working_memory(self):
        """Test patched prompt when no working memory."""
        mock_ga = MagicMock()
        original_prompt = "Original system prompt"
        mock_ga.get_system_prompt = MagicMock(return_value=original_prompt)
        
        with patch.dict('sys.modules', {'generic_agent': MagicMock(GenericAgent=mock_ga)}):
            with patch('genericagent_nmem.read_working_memory', return_value=""):
                genericagent_nmem._INSTALLED = False
                genericagent_nmem.install()
                
                instance = mock_ga()
                result = mock_ga.get_system_prompt(instance)
                
                assert "[Memory]" in result
                assert "WORKING MEMORY" not in result


class TestCompactJsonText:
    """Test _compact_json_text helper."""
    
    def test_compact_json_dict_with_content(self):
        """Test compacting JSON dict with content key."""
        json_str = '{"content": "Test content", "other": "data"}'
        result = genericagent_nmem._compact_json_text(json_str, 1000)
        assert result == "Test content"
    
    def test_compact_json_list(self):
        """Test compacting JSON list."""
        json_str = '["item1", "item2", "item3"]'
        result = genericagent_nmem._compact_json_text(json_str, 1000)
        assert "item1" in result
    
    def test_compact_json_max_chars(self):
        """Test max_chars truncation."""
        json_str = '{"content": "' + ("x" * 1000) + '"}'
        result = genericagent_nmem._compact_json_text(json_str, 100)
        assert len(result) <= 100
    
    def test_compact_json_invalid(self):
        """Test with invalid JSON."""
        result = genericagent_nmem._compact_json_text("not json", 1000)
        assert result == "not json"
    
    def test_compact_json_empty(self):
        """Test with empty string."""
        result = genericagent_nmem._compact_json_text("", 1000)
        assert result == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
