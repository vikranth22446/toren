#!/usr/bin/env python3
"""
Job Manager for Claude Agent Background Execution
Handles job state, progress tracking, and dashboard functionality
"""

import fcntl
import json
import os
import subprocess
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class JobManager:
    # Maximum JSON file size (1MB) to prevent DoS
    MAX_JSON_SIZE = 1024 * 1024

    # Timeout constants (in seconds)
    DOCKER_INSPECT_TIMEOUT = 15
    DOCKER_STOP_TIMEOUT = 10
    DOCKER_REMOVE_TIMEOUT = 10
    DOCKER_RMI_TIMEOUT = 30
    GIT_STATS_TIMEOUT = 30
    PROCESS_WAIT_TIMEOUT = 5

    # Required job data keys for validation
    REQUIRED_JOB_KEYS = {
        "job_id",
        "status",
        "task_spec",
        "branch_name",
        "base_branch",
        "base_image",
        "created_at",
        "updated_at",
    }
    # Valid job status values
    VALID_STATUSES = {"queued", "running", "completed", "failed", "cancelled"}

    def __init__(self):
        # Path.home() temporariyl full TODO FIXME
        self.jobs_dir = Path.cwd() / ".ai_agent" / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _validate_json_size(self, file_path: Path) -> bool:
        """Validate JSON file size to prevent DoS"""
        try:
            return file_path.stat().st_size <= self.MAX_JSON_SIZE
        except OSError:
            return False

    def _validate_job_data(self, data: Dict[str, Any]) -> bool:
        """Validate job data structure and content"""
        if not isinstance(data, dict):
            return False

        # Check required keys
        if not self.REQUIRED_JOB_KEYS.issubset(data.keys()):
            return False

        # Validate status
        if data.get("status") not in self.VALID_STATUSES:
            return False

        # Validate string fields are actually strings
        string_fields = [
            "job_id",
            "status",
            "task_spec",
            "branch_name",
            "base_branch",
            "base_image",
            "created_at",
            "updated_at",
        ]
        for field in string_fields:
            if not isinstance(data.get(field), str):
                return False

        # Validate progress_log is a list if present
        if "progress_log" in data and not isinstance(data["progress_log"], list):
            return False

        return True

    def _safe_load_job(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Safely load and validate job data from JSON file"""
        if not self._validate_json_size(file_path):
            return None

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            if not self._validate_job_data(data):
                return None

            return data
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return None

    @contextmanager
    def _lock_job_file(self, job_id: str):
        """Context manager for atomic job file operations"""
        lock_file = self.jobs_dir / f"{job_id}.lock"
        try:
            with open(lock_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                yield
        finally:
            try:
                lock_file.unlink(missing_ok=True)
            except OSError:
                pass

    @contextmanager
    def _atomic_write(self, target_file: Path):
        """Context manager for atomic file writes with proper temp file cleanup"""
        temp_file = None
        try:
            # Create temp file in same directory to ensure atomic move
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=".tmp", prefix=f"{target_file.name}.", dir=target_file.parent
            )
            os.close(temp_fd)  # Close the file descriptor, we'll use the path
            temp_file = Path(temp_path)
            yield temp_file
            # Atomic move on successful completion
            temp_file.replace(target_file)
            temp_file = None  # Prevent cleanup since move succeeded
        except Exception:
            raise
        finally:
            # Clean up temp file if it still exists (due to exception)
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

    def create_job(
        self,
        task_spec: str,
        base_image: str,
        branch_name: str,
        base_branch: str,
        github_issue: Optional[str] = None,
        cli_type: str = "claude",
    ) -> str:
        """Create a new background job"""
        job_id = str(uuid.uuid4())[:8]

        job_data: Dict[str, Any] = {
            "job_id": job_id,
            "status": "queued",
            "task_spec": task_spec,
            "ai_summary": self._generate_initial_summary(task_spec, cli_type),
            "branch_name": branch_name,
            "base_branch": base_branch,
            "base_image": base_image,
            "github_issue": github_issue,
            "container_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "progress_log": [],
            "pr_url": None,
            "error_message": None,
            "cost_info": {
                "total_cost": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "session_duration": 0,
            },
            "git_stats": {
                "lines_added": 0,
                "lines_deleted": 0,
                "total_lines_changed": 0,
                "files_changed": 0,
                "commits_made": 0,
            },
        }

        job_file = self.jobs_dir / f"{job_id}.json"
        with self._lock_job_file(job_id):
            with self._atomic_write(job_file) as temp_file:
                with open(temp_file, "w") as f:
                    json.dump(job_data, f, indent=2)

        return job_id

    def _generate_initial_summary(
        self, task_spec: str, cli_type: str = "claude"
    ) -> str:
        """Generate AI summary of the task"""
        try:
            import subprocess

            from ai_cli_interface import AICliInterface

            # Create prompt to generate 5-word title
            summary_prompt = f"""Generate exactly 5 words that summarize this task specification:

{task_spec}

Return only the 5-word title, nothing else."""

            # Use specified CLI to generate summary
            ai_cli = AICliInterface(cli_type)
            result = subprocess.run(
                [ai_cli.config["command"], ai_cli.config["print_flag"], summary_prompt],
                capture_output=True,
                text=True,
                timeout=self.DOCKER_INSPECT_TIMEOUT,
            )

            if result.returncode == 0 and result.stdout.strip():
                ai_summary = result.stdout.strip()
                # Clean up the response
                if ai_summary.startswith('"') and ai_summary.endswith('"'):
                    ai_summary = ai_summary[1:-1]

                # Ensure it's roughly 5 words (allow some flexibility)
                words = ai_summary.split()
                if 3 <= len(words) <= 7:
                    return ai_summary

        except subprocess.TimeoutExpired:
            print("ℹ️ AI summary generation timed out, using fallback")
        except subprocess.CalledProcessError as e:
            print(
                f"ℹ️ AI summary generation failed (exit code {e.returncode}), using fallback"
            )
        except OSError as e:
            print(f"ℹ️ Could not execute {cli_type} command: {e}, using fallback")

        # Fallback: Extract key words from first line
        first_line = task_spec.strip().split("\n")[0] if task_spec.strip() else ""
        words = first_line.split()[:5]

        return " ".join(words) if words else "Task processing..."

    def update_job_status(
        self,
        job_id: str,
        status: str,
        container_id: Optional[str] = None,
        agent_image: Optional[str] = None,
        progress_message: Optional[str] = None,
        error_message: Optional[str] = None,
        pr_url: Optional[str] = None,
    ) -> bool:
        """Update job status and metadata"""
        job_file = self.jobs_dir / f"{job_id}.json"
        if not job_file.exists():
            return False

        try:
            with self._lock_job_file(job_id):
                job_data = self._safe_load_job(job_file)
                if job_data is None:
                    return False

                job_data["status"] = status
                job_data["updated_at"] = datetime.now(timezone.utc).isoformat()

                if container_id:
                    job_data["container_id"] = container_id
                if agent_image:
                    job_data["agent_image"] = agent_image
                if progress_message:
                    job_data["progress_log"].append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "message": progress_message,
                        }
                    )
                if error_message:
                    job_data["error_message"] = error_message
                if pr_url:
                    job_data["pr_url"] = pr_url

                # Use atomic write with temporary file and proper cleanup
                with self._atomic_write(job_file) as temp_file:
                    with open(temp_file, "w") as f:
                        json.dump(job_data, f, indent=2)

            return True
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error updating job {job_id} - data serialization error: {e}")
            return False
        except PermissionError as e:
            print(f"Error updating job {job_id} - permission denied: {e}")
            return False
        except OSError as e:
            print(f"Error updating job {job_id} - file system error: {e}")
            return False

    def update_job_cost_info(
        self, job_id: str, cost_info: Dict[str, Any], git_stats: Dict[str, Any]
    ) -> bool:
        """Update job with cost and git statistics"""
        job_file = self.jobs_dir / f"{job_id}.json"
        if not job_file.exists():
            return False

        try:
            with self._lock_job_file(job_id):
                job_data = self._safe_load_job(job_file)
                if job_data is None:
                    return False

                # Update cost information
                job_data["cost_info"].update(
                    {
                        "total_cost": cost_info.get("total_cost", 0.0),
                        "input_tokens": cost_info.get("input_tokens", 0),
                        "output_tokens": cost_info.get("output_tokens", 0),
                        "session_duration": cost_info.get("session_duration", 0),
                    }
                )

                # Update git statistics
                job_data["git_stats"].update(
                    {
                        "lines_added": git_stats.get("lines_added", 0),
                        "lines_deleted": git_stats.get("lines_deleted", 0),
                        "total_lines_changed": git_stats.get("total_lines_changed", 0),
                        "files_changed": git_stats.get("files_changed", 0),
                        "commits_made": git_stats.get("commits_made", 0),
                    }
                )

                job_data["updated_at"] = datetime.now(timezone.utc).isoformat()

                with self._atomic_write(job_file) as temp_file:
                    with open(temp_file, "w") as f:
                        json.dump(job_data, f, indent=2)

                return True

        except (json.JSONDecodeError, ValueError) as e:
            print(
                f"Error updating job cost info {job_id} - data serialization error: {e}"
            )
            return False
        except PermissionError as e:
            print(f"Error updating job cost info {job_id} - permission denied: {e}")
            return False
        except OSError as e:
            print(f"Error updating job cost info {job_id} - file system error: {e}")
            return False

    def _extract_and_update_cost_data(self, job_id: str) -> None:
        """Extract cost data from container output and update job"""
        try:
            cost_data_file = Path.cwd() / ".ai_cost_data" / job_id / "session_cost.json"

            if cost_data_file.exists():
                with open(cost_data_file, "r") as f:
                    session_data = json.load(f)

                # Extract cost info
                cost_info = {
                    "total_cost": session_data.get("summary", {}).get(
                        "total_cost", 0.0
                    ),
                    "input_tokens": session_data.get("cost", {}).get("input_tokens", 0),
                    "output_tokens": session_data.get("cost", {}).get(
                        "output_tokens", 0
                    ),
                    "session_duration": self._calculate_session_duration(session_data),
                }

                # Extract git stats
                git_stats = session_data.get("git_stats", {})

                # Update job with cost information
                success = self.update_job_cost_info(job_id, cost_info, git_stats)

                if success:
                    print(
                        f"💰 Updated job {job_id} with cost: ${cost_info['total_cost']:.4f}"
                    )
                else:
                    print(f"⚠️  Failed to update job {job_id} with cost data")

                # Keep cost data file for future reference
                # Note: Cost data is preserved for debugging and analysis

            else:
                print(f"⚠️  No cost data file found for job {job_id}")

        except (json.JSONDecodeError, ValueError) as e:
            print(
                f"❌ Error extracting cost data for job {job_id} - invalid data format: {e}"
            )
        except FileNotFoundError:
            print(
                f"❌ Error extracting cost data for job {job_id} - cost file not found"
            )
        except PermissionError:
            print(f"❌ Error extracting cost data for job {job_id} - permission denied")
        except OSError as e:
            print(
                f"❌ Error extracting cost data for job {job_id} - file system error: {e}"
            )

    def _calculate_session_duration(self, session_data: Dict[str, Any]) -> int:
        """Calculate session duration in seconds"""
        try:
            from datetime import datetime

            start_str = session_data.get("session_start")
            end_str = session_data.get("last_update")

            if start_str and end_str:
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                duration = (end - start).total_seconds()
                return int(duration)
        except (ValueError, TypeError, KeyError) as e:
            print(f"⚠️ Could not calculate session duration: {type(e).__name__}: {e}")
        return 0

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details by ID"""
        job_file = self.jobs_dir / f"{job_id}.json"
        if not job_file.exists():
            return None

        try:
            with self._lock_job_file(job_id):
                return self._safe_load_job(job_file)
        except FileNotFoundError:
            return None  # Job doesn't exist
        except PermissionError:
            print(f"⚠️ Permission denied accessing job {job_id}")
            return None
        except (json.JSONDecodeError, ValueError) as e:
            print(f"⚠️ Corrupted job file for {job_id}: {e}")
            return None
        except OSError as e:
            print(f"⚠️ Error accessing job {job_id}: {e}")
            return None

    def sync_job_statuses(self) -> None:
        """Sync job statuses with actual container states"""
        jobs = []
        for job_file in self.jobs_dir.glob("*.json"):
            job_data = self._safe_load_job(job_file)
            if job_data is None:
                continue
            jobs.append(job_data)

        for job in jobs:
            job_id = job.get("job_id")
            container_id = job.get("container_id")
            current_status = job.get("status")

            # Only check jobs that think they're running/queued
            if current_status in ["running", "queued"] and container_id:
                try:
                    # Check if container exists and get its status
                    result = subprocess.run(
                        [
                            "docker",
                            "inspect",
                            container_id,
                            "--format",
                            "{{.State.Status}}",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=self.DOCKER_STOP_TIMEOUT,
                    )

                    if result.returncode != 0:
                        # Container doesn't exist anymore
                        self.update_job_status(
                            job_id,
                            "failed",
                            error_message="Container stopped unexpectedly",
                        )
                    else:
                        status = result.stdout.strip()
                        if status == "exited":
                            # Check exit code
                            exit_result = subprocess.run(
                                [
                                    "docker",
                                    "inspect",
                                    container_id,
                                    "--format",
                                    "{{.State.ExitCode}}",
                                ],
                                capture_output=True,
                                text=True,
                                timeout=self.DOCKER_STOP_TIMEOUT,
                            )

                            if (
                                exit_result.returncode == 0
                                and exit_result.stdout.strip() == "0"
                            ):
                                # Job completed successfully
                                self._extract_and_update_cost_data(job_id)
                                self.update_job_status(job_id, "completed")
                            else:
                                self.update_job_status(
                                    job_id,
                                    "failed",
                                    error_message=f"Container exited with code {exit_result.stdout.strip()}",
                                )
                        elif status == "running" and current_status == "queued":
                            self.update_job_status(job_id, "running")

                except subprocess.CalledProcessError as e:
                    # Docker command failed
                    self.update_job_status(
                        job_id,
                        "failed",
                        error_message=f"Docker status check failed: {e.stderr or e}",
                    )
                except subprocess.TimeoutExpired:
                    # Docker command timed out
                    self.update_job_status(
                        job_id, "failed", error_message="Docker status check timed out"
                    )
                except OSError as e:
                    # Docker not available
                    self.update_job_status(
                        job_id, "failed", error_message=f"Docker unavailable: {e}"
                    )

    def list_jobs(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all jobs, optionally filtered by status"""
        # Sync job statuses with actual container states first
        self.sync_job_statuses()

        jobs = []

        for job_file in self.jobs_dir.glob("*.json"):
            job_data = self._safe_load_job(job_file)
            if job_data is None:
                continue

            if status_filter is None or job_data.get("status") == status_filter:
                jobs.append(job_data)

        # Sort by creation time, newest first
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return jobs

    def cleanup_job(self, job_id: str) -> bool:
        """Clean up completed/failed job"""
        job_data = self.get_job(job_id)
        if not job_data:
            return False

        container_id = job_data.get("container_id")
        agent_image = job_data.get("agent_image")
        print(f"Cleaning up job {job_id}...", container_id, agent_image)
        if container_id:
            try:
                if job_data.get("status") in ["running", "queued", "completed"]:
                    subprocess.run(
                        ["docker", "kill", container_id],
                        capture_output=True,
                        timeout=self.DOCKER_STOP_TIMEOUT,
                    )

                # Remove container
                subprocess.run(
                    ["docker", "rm", container_id],
                    capture_output=True,
                    timeout=self.DOCKER_REMOVE_TIMEOUT,
                )
            except (subprocess.SubprocessError, subprocess.TimeoutExpired, OSError):
                pass

        # Remove agent image if it was created for this job
        if agent_image and ("-agent-" in agent_image):
            try:
                subprocess.run(
                    ["docker", "rmi", agent_image],
                    capture_output=True,
                    timeout=self.DOCKER_RMI_TIMEOUT,
                )
            except (subprocess.SubprocessError, subprocess.TimeoutExpired, OSError):
                pass

        # Clean up cost data directory if it exists
        try:
            from pathlib import Path

            cost_data_dir = Path.cwd() / ".ai_cost_data" / job_id
            if cost_data_dir.exists():
                import shutil

                shutil.rmtree(cost_data_dir, ignore_errors=True)
        except (OSError, PermissionError):
            pass  # Ignore cleanup errors for cost data

        # Remove job file atomically
        job_file = self.jobs_dir / f"{job_id}.json"
        try:
            with self._lock_job_file(job_id):
                job_file.unlink(missing_ok=True)
            return True
        except PermissionError:
            print(f"⚠️ Permission denied removing job {job_id}")
            return False
        except OSError as e:
            print(f"⚠️ Error removing job {job_id}: {e}")
            return False

    def cleanup_completed_jobs(self) -> int:
        """Clean up all completed/failed jobs"""
        completed_statuses = ["completed", "failed", "cancelled"]
        jobs = self.list_jobs()
        cleaned = 0

        for job in jobs:
            if job.get("status") in completed_statuses:
                if self.cleanup_job(job["job_id"]):
                    cleaned += 1

        return cleaned

    def get_container_logs(self, job_id: str) -> Optional[str]:
        """Get Docker container logs for a job"""
        job_data = self.get_job(job_id)
        if not job_data or not job_data.get("container_id"):
            return None

        try:
            result = subprocess.run(
                ["docker", "logs", job_data["container_id"]],
                capture_output=True,
                text=True,
                timeout=self.GIT_STATS_TIMEOUT,
            )

            return result.stdout + result.stderr
        except subprocess.CalledProcessError as e:
            return f"Error getting logs - Docker command failed: {e.stderr or e}"
        except subprocess.TimeoutExpired:
            return "Error getting logs - operation timed out"
        except OSError as e:
            return f"Error getting logs - Docker not available: {e}"
        except KeyError:
            return "Error getting logs - job missing container ID"

    def monitor_job(self, job_id: str, container_id: str):
        """Monitor job progress in background thread"""

        def monitor():
            while True:
                try:
                    # Check container status
                    result = subprocess.run(
                        [
                            "docker",
                            "inspect",
                            container_id,
                            "--format",
                            "{{.State.Status}}",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=self.DOCKER_STOP_TIMEOUT,
                    )

                    if result.returncode != 0:
                        # Container doesn't exist anymore
                        self.update_job_status(
                            job_id,
                            "failed",
                            error_message="Container stopped unexpectedly",
                        )
                        break

                    status = result.stdout.strip()

                    if status == "exited":
                        # Check exit code
                        exit_result = subprocess.run(
                            [
                                "docker",
                                "inspect",
                                container_id,
                                "--format",
                                "{{.State.ExitCode}}",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=self.DOCKER_STOP_TIMEOUT,
                        )

                        if (
                            exit_result.returncode == 0
                            and exit_result.stdout.strip() == "0"
                        ):
                            # Job completed successfully - extract cost data
                            self._extract_and_update_cost_data(job_id)
                            self.update_job_status(job_id, "completed")
                        else:
                            self.update_job_status(
                                job_id,
                                "failed",
                                error_message=f"Container exited with code {exit_result.stdout.strip()}",
                            )
                        break

                    elif status == "running":
                        self.update_job_status(job_id, "running")

                    time.sleep(10)  # Check every 10 seconds (faster monitoring)

                except subprocess.CalledProcessError as e:
                    self.update_job_status(
                        job_id,
                        "failed",
                        error_message=f"Docker monitoring failed: {e.stderr or e}",
                    )
                except subprocess.TimeoutExpired:
                    self.update_job_status(
                        job_id, "failed", error_message="Docker monitoring timed out"
                    )
                except OSError as e:
                    self.update_job_status(
                        job_id,
                        "failed",
                        error_message=f"Docker unavailable during monitoring: {e}",
                    )
                    break

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

        # Immediate status check (don't wait for first polling cycle)
        def immediate_check():
            time.sleep(2)  # Give container a moment to start
            try:
                result = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        container_id,
                        "--format",
                        "{{.State.Status}}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=self.PROCESS_WAIT_TIMEOUT,
                )
                if result.returncode == 0:
                    status = result.stdout.strip()
                    if status == "exited":
                        # Container already exited, force monitoring thread to check immediately
                        pass  # The daemon thread will pick it up in next cycle
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
                pass  # Ignore immediate check errors - daemon thread will handle it

        # Start immediate check in background
        immediate_thread = threading.Thread(target=immediate_check, daemon=True)
        immediate_thread.start()


class TimeoutMonitor:
    """Monitor job execution time and notify when time limit is reached"""

    def __init__(self, job_id: str, timelimit_seconds: int, github_utils=None):
        self.job_id = job_id
        self.timelimit_seconds = timelimit_seconds
        self.github_utils = github_utils
        self.start_time = time.time()
        self.monitor_thread = None
        self.stop_monitoring = threading.Event()

    def start_monitoring(self):
        """Start the background monitoring thread"""
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.monitor_thread = threading.Thread(target=self._monitor, daemon=True)
            self.monitor_thread.start()

    def stop_monitoring_thread(self):
        """Stop the background monitoring thread"""
        self.stop_monitoring.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)

    def _monitor(self):
        """Background thread that monitors execution time"""
        while not self.stop_monitoring.wait(timeout=5):  # Check every 5 seconds
            elapsed_time = time.time() - self.start_time
            
            if elapsed_time >= self.timelimit_seconds:
                # Time limit reached, send notification
                self._send_timeout_notification(elapsed_time)
                break

    def _send_timeout_notification(self, elapsed_time: float):
        """Send GitHub notification when time limit is reached"""
        try:
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            
            message = (
                f"⏰ **Time Limit Reached**\n\n"
                f"Job `{self.job_id}` has exceeded the specified time limit of "
                f"{self.timelimit_seconds // 60} minutes.\n\n"
                f"**Elapsed Time:** {minutes}m {seconds}s\n\n"
                f"The agent is still running but may need manual intervention "
                f"or additional time to complete the task."
            )
            
            if self.github_utils:
                # Try to send a PR comment notification
                try:
                    self.github_utils.notify_progress(f"Time limit reached: {minutes}m {seconds}s elapsed")
                except Exception as e:
                    print(f"⚠️ Failed to send GitHub notification: {e}")
                    
        except Exception as e:
            print(f"⚠️ Error in timeout notification: {e}")

    def get_elapsed_time(self) -> float:
        """Get the elapsed time in seconds"""
        return time.time() - self.start_time

    def get_remaining_time(self) -> float:
        """Get the remaining time in seconds (negative if exceeded)"""
        return self.timelimit_seconds - self.get_elapsed_time()
