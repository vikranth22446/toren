#!/usr/bin/env python3
"""
TimeoutMonitor - Handles execution time limits for agent jobs
"""

import threading
import time
from typing import Optional

from github_utils import GitHubUtils


class TimeoutMonitor:
    """Monitors agent execution time and sends notifications when time limit is reached"""

    def __init__(self, timelimit: int, job_id: str, pr_number: Optional[str] = None):
        self.timelimit = timelimit
        self.job_id = job_id
        self.pr_number = pr_number
        self.github_utils = GitHubUtils()
        self._timer_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started = False

    def start(self) -> None:
        """Start the timeout monitoring in a background thread"""
        if self._started:
            return

        self._started = True
        self._timer_thread = threading.Thread(target=self._monitor_timeout, daemon=True)
        self._timer_thread.start()

    def stop(self) -> None:
        """Stop the timeout monitoring"""
        if self._stop_event:
            self._stop_event.set()

    def _monitor_timeout(self) -> None:
        """Background thread that monitors timeout"""
        self._stop_event.wait(timeout=self.timelimit)

        if not self._stop_event.is_set():
            self._handle_timeout()

    def _handle_timeout(self) -> None:
        """Handle timeout by sending GitHub PR comment notification"""
        timeout_message = f"""🕐 **Timeout Alert**

Agent job `{self.job_id}` has reached the time limit of {self.timelimit} seconds ({self.timelimit // 60} minutes).

The agent is still running but may need attention or manual intervention.

🤖 Automated timeout notification"""

        try:
            if self.pr_number:
                self.github_utils.comment_on_pr(self.pr_number, timeout_message)
                print(f"⏰ Timeout notification sent to PR #{self.pr_number} for job {self.job_id}")
            else:
                print(f"⏰ Job {self.job_id} timed out after {self.timelimit} seconds")
        except Exception as e:
            print(f"❌ Failed to send timeout notification: {e}")