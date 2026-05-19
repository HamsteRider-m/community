"""Tests for session_save module."""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from session_save import SessionParser, NmemClient


class TestSessionParser(unittest.TestCase):
    """Test SessionParser functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_log(self, filename: str, content: str) -> Path:
        """Helper to create a test log file."""
        log_file = self.temp_path / filename
        log_file.write_text(content, encoding="utf-8")
        return log_file
    
    def test_parse_valid_log(self):
        """Test parsing a valid log file with real GA format."""
        # Use actual GA log format
        content = """=== Prompt === 2026-05-19 01:26:51
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "Hello"
    }
  ]
}

=== Response === 2026-05-19 01:26:59
[{'type': 'text', 'text': 'Hi there'}]

=== Prompt === 2026-05-19 01:27:01
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "How are you?"
    }
  ]
}

=== Response === 2026-05-19 01:27:05
[{'type': 'text', 'text': "I'm good"}]
"""
        log_file = self.create_test_log("model_responses_12345.txt", content)
        result = SessionParser.parse_log_file(log_file)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["session_id"], "12345")
        self.assertEqual(result["thread_id"], "ga-12345")
        self.assertEqual(result["title"], "Hello")
        # Parser extracts text-only messages (2 user + 2 assistant = 4)
        self.assertEqual(len(result["messages"]), 4)
        self.assertEqual(result["messages"][0]["role"], "user")
        self.assertEqual(result["messages"][0]["content"], "Hello")
        self.assertEqual(result["messages"][1]["role"], "assistant")
        self.assertEqual(result["messages"][1]["content"], "Hi there")
    
    def test_parse_single_message(self):
        """Test parsing a log with single message pair."""
        content = """=== Prompt === 2026-04-27 14:09:23
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "Test"
    }
  ]
}

=== Response === 2026-04-27 14:09:26
[{'type': 'text', 'text': 'Response'}]
"""
        log_file = self.create_test_log("model_responses_11111.txt", content)
        result = SessionParser.parse_log_file(log_file)
        
        self.assertIsNotNone(result)
        # One user message + one assistant message = 2
        self.assertEqual(len(result["messages"]), 2)
    
    def test_parse_empty_file(self):
        """Test parsing an empty file."""
        log_file = self.create_test_log("model_responses_99999.txt", "")
        result = SessionParser.parse_log_file(log_file)
        
        self.assertIsNone(result)
    
    def test_title_truncation(self):
        """Test that long titles are truncated."""
        long_content = "A" * 300
        content = f"""=== Prompt === 2026-05-19 01:26:51
{{
  "role": "user",
  "content": [
    {{
      "type": "text",
      "text": "{long_content}"
    }}
  ]
}}

=== Response === 2026-05-19 01:26:59
[{{'type': 'text', 'text': 'Response'}}]
"""
        log_file = self.create_test_log("model_responses_77777.txt", content)
        result = SessionParser.parse_log_file(log_file)
        
        self.assertIsNotNone(result)
        # Title is truncated to 100 chars + "..."
        self.assertLessEqual(len(result["title"]), 104)
        self.assertTrue(result["title"].endswith("..."))


class TestNmemClient(unittest.TestCase):
    """Test NmemClient functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use correct parameter name: api_url
        self.client = NmemClient(api_url="http://test.local:3721")
    
    @patch('session_save.urlopen')
    def test_create_thread_success(self, mock_urlopen):
        """Test successful thread creation."""
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "thread": {"thread_id": "ga-123", "title": "Test"},
            "messages": []
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        result = self.client.create_thread(
            thread_id="ga-123",
            title="Test",
            messages=[{"role": "user", "content": "Hello"}]
        )
        
        self.assertEqual(result, "ga-123")
    
    @patch('session_save.urlopen')
    def test_append_thread_success(self, mock_urlopen):
        """Test successful message append."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "messages_added": 2,
            "total_messages": 5
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        result = self.client.append_thread(
            thread_id="ga-123",
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"}
            ]
        )
        
        self.assertEqual(result["messages_added"], 2)
        self.assertEqual(result["total_messages"], 5)
    
    def test_create_thread_validation(self):
        """Test input validation for create_thread."""
        with self.assertRaises(ValueError):
            self.client.create_thread(
                thread_id="",
                title="Test",
                messages=[]
            )
        
        with self.assertRaises(ValueError):
            self.client.create_thread(
                thread_id="ga-123",
                title="",
                messages=[]
            )
    
    def test_append_thread_validation(self):
        """Test input validation for append_thread."""
        with self.assertRaises(ValueError):
            self.client.append_thread(
                thread_id="",
                messages=[{"role": "user", "content": "Hello"}]
            )
        
        # Empty messages returns early
        result = self.client.append_thread(
            thread_id="ga-123",
            messages=[]
        )
        self.assertEqual(result["messages_added"], 0)


if __name__ == "__main__":
    unittest.main()
