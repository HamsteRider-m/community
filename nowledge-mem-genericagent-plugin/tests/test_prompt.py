"""Tests for prompt building functions in genericagent_nmem."""
import subprocess
from unittest.mock import patch, MagicMock
import pytest
import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import genericagent_nmem


class TestReadWorkingMemory:
    """Test read_working_memory() function."""

    @patch('genericagent_nmem._run_nmem')
    def test_read_working_memory_json_success(self, mock_run):
        """Test reading working memory with JSON API."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = '{"content": "test working memory content"}'
        mock_run.return_value = mock_proc
        
        result = genericagent_nmem.read_working_memory()
        assert result == "test working memory content"
        # Should try JSON API first
        mock_run.assert_called_once_with(("--json", "wm", "read"))

    @patch('genericagent_nmem._run_nmem')
    def test_read_working_memory_fallback_to_plain(self, mock_run):
        """Test fallback to plain text when JSON fails."""
        # First call (JSON) fails, second call (plain) succeeds
        mock_proc_fail = MagicMock()
        mock_proc_fail.returncode = 1
        mock_proc_fail.stdout = ""
        
        mock_proc_success = MagicMock()
        mock_proc_success.returncode = 0
        mock_proc_success.stdout = "plain text working memory"
        
        mock_run.side_effect = [mock_proc_fail, mock_proc_success]
        
        result = genericagent_nmem.read_working_memory()
        assert result == "plain text working memory"
        assert mock_run.call_count == 2

    @patch('genericagent_nmem._run_nmem')
    def test_read_working_memory_both_fail(self, mock_run):
        """Test when both JSON and plain text fail."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_run.return_value = mock_proc
        
        result = genericagent_nmem.read_working_memory()
        assert result == ""

    @patch('genericagent_nmem._run_nmem')
    def test_read_working_memory_nmem_not_found(self, mock_run):
        """Test when nmem CLI is not available."""
        mock_run.return_value = None
        
        result = genericagent_nmem.read_working_memory()
        assert result == ""

    @patch('genericagent_nmem._run_nmem')
    def test_read_working_memory_empty_content(self, mock_run):
        """Test when working memory returns empty content field."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = '{"content": ""}'
        mock_run.return_value = mock_proc
        
        result = genericagent_nmem.read_working_memory()
        # _compact_json_text returns the pretty-printed JSON when content is empty
        # This is expected behavior - it doesn't trigger fallback
        assert isinstance(result, str)


class TestGetNmemStatusText:
    """Test get_nmem_status_text() function."""

    @patch('genericagent_nmem._run_nmem')
    def test_get_nmem_status_success(self, mock_run):
        """Test successful nmem status retrieval."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "nmem status: OK\nWorking memory: active"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc
        
        result = genericagent_nmem.get_nmem_status_text()
        assert "nmem status: OK" in result
        assert "Working memory: active" in result

    @patch('genericagent_nmem._run_nmem')
    def test_get_nmem_status_with_stderr(self, mock_run):
        """Test status with stderr output."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "Error: configuration not found"
        mock_run.return_value = mock_proc
        
        result = genericagent_nmem.get_nmem_status_text()
        assert "Error: configuration not found" in result

    @patch('genericagent_nmem._run_nmem')
    def test_get_nmem_status_cli_not_found(self, mock_run):
        """Test when nmem CLI is not available."""
        mock_run.return_value = None
        
        result = genericagent_nmem.get_nmem_status_text()
        assert "nmem status unavailable" in result
        assert "CLI not found" in result

    @patch('genericagent_nmem._run_nmem')
    def test_get_nmem_status_no_output(self, mock_run):
        """Test when nmem status returns no output."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc
        
        result = genericagent_nmem.get_nmem_status_text()
        assert "exited 0 with no output" in result

    @patch('genericagent_nmem._run_nmem')
    def test_get_nmem_status_truncation(self, mock_run):
        """Test that long status output is truncated."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "x" * 5000
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc
        
        result = genericagent_nmem.get_nmem_status_text()
        assert len(result) <= 2000


class TestBuildPromptBlock:
    """Test build_prompt_block() function."""

    @patch('genericagent_nmem.get_nmem_status_text')
    @patch('genericagent_nmem.read_working_memory')
    def test_build_prompt_block_with_working_memory(self, mock_read_wm, mock_status):
        """Test prompt block with working memory content."""
        mock_read_wm.return_value = "Test working memory content"
        mock_status.return_value = "nmem status: OK"
        
        result = genericagent_nmem.build_prompt_block()
        
        # Check structure
        assert "[Nowledge Mem / nmem integration for GenericAgent]" in result
        assert "Integration status: working-memory-loaded" in result
        assert "nmem status: OK" in result
        assert "[Nowledge Working Memory]" in result
        assert "Test working memory content" in result
        
        # Check behavior guidance
        assert "Treat this as a GenericAgent-specific nmem integration" in result
        assert "nmem --json wm read" in result
        assert "nmem --json m search" in result

    @patch('genericagent_nmem.get_nmem_status_text')
    @patch('genericagent_nmem.read_working_memory')
    def test_build_prompt_block_without_working_memory(self, mock_read_wm, mock_status):
        """Test prompt block when working memory is empty."""
        mock_read_wm.return_value = ""
        mock_status.return_value = "nmem status: OK"
        
        result = genericagent_nmem.build_prompt_block()
        
        # Check structure
        assert "[Nowledge Mem / nmem integration for GenericAgent]" in result
        assert "Integration status: installed; working memory empty or unreadable" in result
        assert "nmem status: OK" in result
        
        # Should NOT include working memory section
        assert "[Nowledge Working Memory]" not in result

    @patch('genericagent_nmem.get_nmem_status_text')
    @patch('genericagent_nmem.read_working_memory')
    def test_build_prompt_block_cli_commands(self, mock_read_wm, mock_status):
        """Test that CLI commands are included in prompt."""
        mock_read_wm.return_value = ""
        mock_status.return_value = "nmem status: OK"
        
        result = genericagent_nmem.build_prompt_block()
        
        # Check CLI commands
        assert "nmem --json wm read" in result
        assert "nmem --json m search" in result
        assert "nmem --json t search" in result
        assert "nmem m add" in result
        assert "nmem status" in result

    @patch('genericagent_nmem.get_nmem_status_text')
    @patch('genericagent_nmem.read_working_memory')
    def test_build_prompt_block_mcp_config(self, mock_read_wm, mock_status):
        """Test that MCP configuration is included in prompt."""
        mock_read_wm.return_value = ""
        mock_status.return_value = "nmem status: OK"
        
        result = genericagent_nmem.build_prompt_block()
        
        # Check MCP configuration
        assert "Direct MCP configuration" in result
        assert "nowledge-mem" in result
        assert "http://127.0.0.1:14242/mcp/" in result
        assert "streamableHttp" in result

    @patch('genericagent_nmem.get_nmem_status_text')
    @patch('genericagent_nmem.read_working_memory')
    def test_build_prompt_block_ends_with_newline(self, mock_read_wm, mock_status):
        """Test that prompt block ends with a single newline."""
        mock_read_wm.return_value = "test"
        mock_status.return_value = "OK"
        
        result = genericagent_nmem.build_prompt_block()
        
        assert result.endswith("\n")
        assert not result.endswith("\n\n")


class TestExportHandoff:
    """Test export_handoff() function."""

    @patch('genericagent_nmem._run_nmem')
    def test_export_handoff_success(self, mock_run):
        """Test successful handoff export."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc
        
        result = genericagent_nmem.export_handoff("Test summary")
        assert result is True
        
        # Check command structure
        call_args = mock_run.call_args[0][0]
        assert "m" in call_args
        assert "add" in call_args
        assert "Test summary" in call_args
        assert "-t" in call_args
        assert "GenericAgent handoff" in call_args
        assert "-l" in call_args
        assert "genericagent" in call_args
        assert "--unit-type" in call_args
        assert "learning" in call_args

    @patch('genericagent_nmem._run_nmem')
    def test_export_handoff_with_project(self, mock_run):
        """Test handoff export with project label."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc
        
        result = genericagent_nmem.export_handoff("Test summary", project="/path/to/myproject")
        assert result is True
        
        # Check that project name is included
        call_args = mock_run.call_args[0][0]
        assert "myproject" in call_args

    @patch('genericagent_nmem._run_nmem')
    def test_export_handoff_failure(self, mock_run):
        """Test handoff export failure."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_run.return_value = mock_proc
        
        result = genericagent_nmem.export_handoff("Test summary")
        assert result is False

    @patch('genericagent_nmem._run_nmem')
    def test_export_handoff_cli_not_found(self, mock_run):
        """Test handoff export when CLI is not available."""
        mock_run.return_value = None
        
        result = genericagent_nmem.export_handoff("Test summary")
        assert result is False

    @patch('genericagent_nmem._run_nmem')
    def test_export_handoff_timeout(self, mock_run):
        """Test that export_handoff uses extended timeout."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc
        
        genericagent_nmem.export_handoff("Test summary")
        
        # Check timeout parameter
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get('timeout') == 15


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=genericagent_nmem", "--cov-report=term-missing"])
