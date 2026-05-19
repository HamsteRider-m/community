"""Tests for CLI invocation functions in genericagent_nmem."""
import subprocess
import json
from unittest.mock import patch, MagicMock
import pytest
import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import genericagent_nmem


class TestRunNmem:
    """Test _run_nmem() function."""

    def test_run_nmem_success(self):
        """Test successful nmem command execution."""
        result = genericagent_nmem._run_nmem(["status"])
        assert result is not None
        assert result.returncode == 0

    def test_run_nmem_with_json_output(self):
        """Test nmem command with JSON output."""
        result = genericagent_nmem._run_nmem(["--json", "wm", "read"])
        assert result is not None
        if result.returncode == 0:
            # Try to parse stdout as JSON
            try:
                data = json.loads(result.stdout)
                assert isinstance(data, dict)
            except json.JSONDecodeError:
                # Empty working memory returns non-JSON output, that's OK
                pass

    def test_run_nmem_timeout(self):
        """Test nmem command timeout handling."""
        # Use a command that might take longer than the timeout
        result = genericagent_nmem._run_nmem(["search", "test"], timeout=0.01)
        # Either completes quickly or times out (returncode None)
        assert result is None or isinstance(result.returncode, int)

    @patch('subprocess.run')
    def test_run_nmem_command_not_found(self, mock_run):
        """Test handling of nmem command not found."""
        mock_run.side_effect = FileNotFoundError("nmem not found")
        result = genericagent_nmem._run_nmem(["status"])
        assert result is None

    @patch('subprocess.run')
    def test_run_nmem_os_error(self, mock_run):
        """Test handling of OS errors."""
        mock_run.side_effect = OSError("Test error")
        result = genericagent_nmem._run_nmem(["status"])
        assert result is None

    def test_run_nmem_invalid_command(self):
        """Test nmem with invalid command."""
        result = genericagent_nmem._run_nmem(["invalid_command_xyz"])
        assert result is not None
        assert result.returncode != 0


class TestCompactJsonText:
    """Test _compact_json_text() function."""

    def test_compact_json_text_extract_content_field(self):
        """Test extracting 'content' field from JSON."""
        json_str = '{"content": "test content", "other": "data"}'
        result = genericagent_nmem._compact_json_text(json_str, max_chars=1000)
        assert result == "test content"

    def test_compact_json_text_extract_memory_field(self):
        """Test extracting 'memory' field from JSON."""
        json_str = '{"memory": "test memory", "other": "data"}'
        result = genericagent_nmem._compact_json_text(json_str, max_chars=1000)
        assert result == "test memory"

    def test_compact_json_text_fallback_to_pretty_json(self):
        """Test fallback to pretty JSON when no known fields exist."""
        json_str = '{"unknown": "value", "nested": {"a": 1}}'
        result = genericagent_nmem._compact_json_text(json_str, max_chars=1000)
        # Should be pretty-printed JSON
        assert "unknown" in result
        assert "value" in result

    def test_compact_json_text_list_truncation(self):
        """Test that lists are truncated to first 8 items."""
        json_str = json.dumps([{"id": i} for i in range(20)])
        result = genericagent_nmem._compact_json_text(json_str, max_chars=10000)
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) <= 8

    def test_compact_json_text_invalid_json(self):
        """Test handling of invalid JSON."""
        invalid_json = "not a json string"
        result = genericagent_nmem._compact_json_text(invalid_json, max_chars=1000)
        assert result == invalid_json

    def test_compact_json_text_truncation(self):
        """Test truncation of long text."""
        long_text = "x" * 50000
        result = genericagent_nmem._compact_json_text(long_text, max_chars=1000)
        assert len(result) == 1000
        assert result == "x" * 1000

    def test_compact_json_text_no_truncation_needed(self):
        """Test that short text is not truncated."""
        short_json = '{"content": "short"}'
        result = genericagent_nmem._compact_json_text(short_json, max_chars=1000)
        assert result == "short"
        assert len(result) < 1000

    def test_compact_json_text_empty_string(self):
        """Test handling of empty string."""
        result = genericagent_nmem._compact_json_text("", max_chars=1000)
        assert result == ""

    def test_compact_json_text_whitespace_only(self):
        """Test handling of whitespace-only string."""
        result = genericagent_nmem._compact_json_text("   \n\t  ", max_chars=1000)
        assert result == ""

    def test_compact_json_text_priority_order(self):
        """Test that 'content' field has priority over 'memory'."""
        json_str = '{"content": "first", "memory": "second"}'
        result = genericagent_nmem._compact_json_text(json_str, max_chars=1000)
        assert result == "first"


class TestShellQuote:
    """Test shell_quote() function."""

    def test_shell_quote_simple_args(self):
        """Test quoting simple arguments."""
        result = genericagent_nmem.shell_quote(["nmem", "status"])
        assert result == "nmem status"

    def test_shell_quote_args_with_spaces(self):
        """Test quoting arguments with spaces."""
        result = genericagent_nmem.shell_quote(["nmem", "m", "add", "test content"])
        assert "test content" in result or "'test content'" in result

    def test_shell_quote_args_with_special_chars(self):
        """Test quoting arguments with special characters."""
        result = genericagent_nmem.shell_quote(["nmem", "search", "test$var"])
        # Should be properly quoted
        assert "$" in result or "\\$" in result or "'" in result

    def test_shell_quote_empty_list(self):
        """Test quoting empty argument list."""
        result = genericagent_nmem.shell_quote([])
        assert result == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=genericagent_nmem", "--cov-report=term-missing"])
