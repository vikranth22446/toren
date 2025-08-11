#!/usr/bin/env python3
"""
Test cases for TimeoutMonitor functionality
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from timeout_monitor import TimeoutMonitor


class TestTimeoutMonitor(unittest.TestCase):
    """Test cases for TimeoutMonitor class"""

    def setUp(self):
        """Set up test fixtures"""
        self.job_id = "test_job_123"
        self.pr_number = "42"
        self.short_timeout = 1  # 1 second for fast tests

    @patch('timeout_monitor.GitHubUtils')
    def test_timeout_monitor_initialization(self, mock_github_utils):
        """Test TimeoutMonitor initializes correctly"""
        monitor = TimeoutMonitor(self.short_timeout, self.job_id, self.pr_number)
        
        self.assertEqual(monitor.timelimit, self.short_timeout)
        self.assertEqual(monitor.job_id, self.job_id)
        self.assertEqual(monitor.pr_number, self.pr_number)
        self.assertFalse(monitor._started)

    @patch('timeout_monitor.GitHubUtils')
    def test_timeout_monitor_start_stop(self, mock_github_utils):
        """Test TimeoutMonitor start and stop functionality"""
        monitor = TimeoutMonitor(self.short_timeout, self.job_id, self.pr_number)
        
        # Test start
        monitor.start()
        self.assertTrue(monitor._started)
        self.assertIsNotNone(monitor._timer_thread)
        
        # Test stop
        monitor.stop()
        self.assertTrue(monitor._stop_event.is_set())

    @patch('timeout_monitor.GitHubUtils')
    def test_timeout_notification(self, mock_github_utils):
        """Test timeout notification is sent"""
        mock_github = MagicMock()
        mock_github_utils.return_value = mock_github
        
        monitor = TimeoutMonitor(self.short_timeout, self.job_id, self.pr_number)
        monitor.start()
        
        # Wait for timeout to trigger
        time.sleep(1.5)
        
        # Verify GitHub comment was called
        mock_github.comment_on_pr.assert_called_once()
        call_args = mock_github.comment_on_pr.call_args
        self.assertEqual(call_args[0][0], self.pr_number)  # PR number
        self.assertIn(self.job_id, call_args[0][1])  # Job ID in message
        self.assertIn("Timeout Alert", call_args[0][1])  # Timeout message

    def test_timeout_without_pr(self):
        """Test timeout handling when no PR number is provided"""
        monitor = TimeoutMonitor(self.short_timeout, self.job_id)
        
        # This should not raise an exception
        monitor._handle_timeout()


if __name__ == '__main__':
    unittest.main()