#!/usr/bin/env python3
"""
Tests for TimeoutMonitor functionality
"""

import time
import unittest
from unittest.mock import Mock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from job_manager import TimeoutMonitor


class TestTimeoutMonitor(unittest.TestCase):
    """Test the TimeoutMonitor class"""

    def setUp(self):
        self.job_id = "test-job-123"
        self.timelimit = 5  # 5 seconds for quick testing
        self.github_utils = Mock()

    def test_timeout_monitor_initialization(self):
        """Test TimeoutMonitor initialization"""
        monitor = TimeoutMonitor(self.job_id, self.timelimit, self.github_utils)
        self.assertEqual(monitor.job_id, self.job_id)
        self.assertEqual(monitor.timelimit_seconds, self.timelimit)
        self.assertEqual(monitor.github_utils, self.github_utils)
        self.assertIsNone(monitor.monitor_thread)

    def test_elapsed_time_calculation(self):
        """Test elapsed time calculation"""
        monitor = TimeoutMonitor(self.job_id, self.timelimit, self.github_utils)
        
        # Wait a small amount of time
        time.sleep(0.1)
        elapsed = monitor.get_elapsed_time()
        self.assertGreater(elapsed, 0.05)  # Should be at least 50ms
        self.assertLess(elapsed, 1.0)     # Should be less than 1 second

    def test_remaining_time_calculation(self):
        """Test remaining time calculation"""
        monitor = TimeoutMonitor(self.job_id, self.timelimit, self.github_utils)
        
        remaining = monitor.get_remaining_time()
        self.assertLessEqual(remaining, self.timelimit)
        self.assertGreater(remaining, self.timelimit - 1)  # Should be close to timelimit

    def test_monitor_thread_lifecycle(self):
        """Test monitor thread can be started and stopped"""
        monitor = TimeoutMonitor(self.job_id, self.timelimit, self.github_utils)
        
        # Start monitoring
        monitor.start_monitoring()
        self.assertIsNotNone(monitor.monitor_thread)
        self.assertTrue(monitor.monitor_thread.is_alive())
        
        # Stop monitoring
        monitor.stop_monitoring_thread()
        time.sleep(0.1)  # Give thread time to stop
        self.assertFalse(monitor.monitor_thread.is_alive())

    @patch('time.time')
    def test_timeout_notification(self, mock_time):
        """Test timeout notification is sent when time limit is reached"""
        # Mock time to simulate timeout
        mock_time.side_effect = [0, 10]  # Start at 0, then jump to 10 seconds
        
        monitor = TimeoutMonitor(self.job_id, 5, self.github_utils)  # 5 second limit
        
        # Manually trigger timeout notification
        monitor._send_timeout_notification(10.0)
        
        # Verify GitHub notification was called
        self.github_utils.notify_progress.assert_called_once()
        call_args = self.github_utils.notify_progress.call_args[0]
        self.assertIn("Time limit reached", call_args[0])

    def test_timeout_monitor_without_github_utils(self):
        """Test TimeoutMonitor works without GitHub utils"""
        monitor = TimeoutMonitor(self.job_id, self.timelimit, None)
        
        # Should not raise exception
        monitor._send_timeout_notification(10.0)
        
        # Basic functionality should still work
        self.assertEqual(monitor.job_id, self.job_id)
        self.assertGreater(monitor.get_elapsed_time(), 0)


if __name__ == "__main__":
    unittest.main()