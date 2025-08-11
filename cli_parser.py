#!/usr/bin/env python3
"""
CLI Parser - Handles command line argument parsing for Claude Agent
"""

import argparse
from typing import Any, Dict


class CLIParser:
    """Handles command line argument parsing and validation"""

    def __init__(self, reviewer_username: str, config: Dict[str, Any]):
        self.reviewer_username = reviewer_username
        self.config = config
        self._parser = None

    def parse_args(self) -> argparse.Namespace:
        """Parse command line arguments"""
        self._parser = argparse.ArgumentParser(
            description="Toren - Multi-AI CLI Agent Runner",
            epilog="""Common workflows:
  Health check:   toren health --docker-image python:3.11 --security
  Start a job:    toren run --base-image python:3.11 --spec task.md --branch fix/auth-bug
  Check status:   toren status
  View logs:      toren logs abc123 --follow
  Clean up:       toren cleanup --all

  ML/AI with GPU:  toren run --base-image pytorch/pytorch:latest \\
                   --spec ml_task.md --branch fix/training \\
                   --env CUDA_VISIBLE_DEVICES=0 --volume /data:/workspace/data

Visit https://github.com/vikranth22446/toren for more information.""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        subparsers = self._parser.add_subparsers(dest="command", help="Available commands")

        self._add_run_parser(subparsers)
        self._add_status_parser(subparsers)
        self._add_summary_parser(subparsers)
        self._add_logs_parser(subparsers)
        self._add_cleanup_parser(subparsers)
        self._add_kill_parser(subparsers)
        self._add_health_parser(subparsers)
        self._add_update_parser(subparsers)

        return self._parser.parse_args()

    def _add_run_parser(self, subparsers):
        """Add run command parser"""
        run_parser = subparsers.add_parser(
            "run",
            help="Start new agent job",
            description=(
                "Launch an AI agent to work on GitHub issues or custom specifications."
            ),
            epilog="""Examples:
  %(prog)s --base-image python:3.11 --spec task.md --branch fix/auth-bug
  %(prog)s --base-image python:3.11 --short "Fix login bug" \\
           --branch fix/login-issue
  %(prog)s --base-image myproject:dev \\
           --issue https://github.com/user/repo/issues/123 \\
           --branch fix/issue-123
  %(prog)s --base-image ubuntu:22.04 --spec task.md \\
           --branch feature/new-api --base-branch develop

  # ML/AI workflows with GPU and model caching:
  %(prog)s --base-image pytorch/pytorch:latest --spec ml_task.md --branch fix/training \\
           --env CUDA_VISIBLE_DEVICES=0 --env HF_HOME=/cache/huggingface \\
           --volume /data/models:/workspace/models --volume /cache/huggingface:/root/.cache/huggingface

  # Custom environment with secrets:
  %(prog)s --base-image python:3.11 --spec api_task.md --branch feature/api \\
           --env API_KEY_PATH=/secrets/api.key --volume /host/secrets:/secrets:ro""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        run_parser.add_argument(
            "--spec", type=str, help="Path to markdown spec file (e.g., task.md)"
        )
        run_parser.add_argument(
            "--short",
            type=str,
            help="Short task description (alternative to --spec file)",
        )
        run_parser.add_argument(
            "--issue",
            type=str,
            help="GitHub issue URL (e.g., https://github.com/owner/repo/issues/123)",
        )
        run_parser.add_argument(
            "--pr",
            type=str,
            help="GitHub PR number to continue working on (reads @claude comments)",
        )
        run_parser.add_argument(
            "--branch",
            type=str,
            help="Branch name to create (e.g., fix/issue-123, feature/new-api). Optional for --pr mode.",
        )
        run_parser.add_argument(
            "--reviewer",
            type=str,
            default=self.reviewer_username,
            help=f"GitHub username to tag for review (default: {self.reviewer_username})",
        )
        run_parser.add_argument(
            "--base-image",
            type=str,
            default=self.config.get("default_base_image"),
            help="Base Docker image to extend with agent tools (e.g., python:3.11, myproject:dev). Default from config.json.",
        )
        run_parser.add_argument(
            "--base-branch",
            type=str,
            default="main",
            help="Base branch to branch from (default: main)",
        )
        run_parser.add_argument(
            "--max-lines",
            type=int,
            default=400,
            help="Maximum lines changed allowed (default: 400)",
        )
        run_parser.add_argument(
            "--warn-lines",
            type=int,
            default=300,
            help="Warning threshold for lines changed (default: 300)",
        )
        run_parser.add_argument(
            "--env",
            action="append",
            help="Environment variables to pass to container (e.g., --env CUDA_VISIBLE_DEVICES=0 --env HF_HOME=/cache)",
        )
        run_parser.add_argument(
            "--volume",
            action="append",
            help="Additional volume mounts (e.g., --volume /host/models:/container/models --volume /cache:/root/.cache)",
        )
        run_parser.add_argument(
            "--language",
            choices=["python", "rust"],
            default="python",
            help="Project language for toolchain setup (default: python)",
        )
        run_parser.add_argument(
            "--cost-estimate",
            action="store_true",
            help="Estimate potential Claude API cost before execution (requires API key)",
        )
        run_parser.add_argument(
            "--cli-type",
            choices=["claude", "gemini"],
            default="claude",
            help="AI CLI to use for the agent (default: claude)",
        )
        run_parser.add_argument(
            "--timelimit",
            type=int,
            default=600,
            help="Time limit for agent execution in seconds (default: 600, i.e., 10 minutes)",
        )

    def _add_status_parser(self, subparsers):
        """Add status command parser"""
        status_parser = subparsers.add_parser(
            "status",
            help="Show job status and progress",
            description="Display running, completed, and failed jobs with progress information.",
            epilog="""Examples:
  %(prog)s                     # Show all jobs
  %(prog)s --job-id abc123     # Show detailed info for specific job
  %(prog)s --filter running    # Show only running jobs""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        status_parser.add_argument(
            "--job-id",
            metavar="JOB_ID",
            help="Show detailed status for specific job (e.g., abc123)",
        )
        status_parser.add_argument(
            "--filter",
            choices=["running", "completed", "failed", "queued"],
            help="Filter jobs by status",
        )

    def _add_summary_parser(self, subparsers):
        """Add summary command parser"""
        summary_parser = subparsers.add_parser(
            "summary",
            help="Show AI-generated task summary",
            description="Display AI-generated summary and progress for a specific job.",
            epilog="""Examples:
  %(prog)s abc123              # Show AI summary for job abc123""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        summary_parser.add_argument(
            "job_id", metavar="JOB_ID", help="Job ID to summarize (e.g., abc123)"
        )

    def _add_logs_parser(self, subparsers):
        """Add logs command parser"""
        logs_parser = subparsers.add_parser(
            "logs",
            help="Show job logs and output",
            description="Display Docker container logs for a running or completed job.",
            epilog="""Examples:
  %(prog)s abc123              # Show logs for job abc123
  %(prog)s abc123 --follow     # Follow logs in real-time (like tail -f)""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        logs_parser.add_argument(
            "job_id", metavar="JOB_ID", help="Job ID to show logs for (e.g., abc123)"
        )
        logs_parser.add_argument(
            "--follow",
            "-f",
            action="store_true",
            help="Follow log output in real-time (like tail -f)",
        )

    def _add_cleanup_parser(self, subparsers):
        """Add cleanup command parser"""
        cleanup_parser = subparsers.add_parser(
            "cleanup",
            help="Clean up completed jobs",
            description="Remove job files and stop containers for completed or failed jobs.",
            epilog="""Examples:
  %(prog)s --all               # Clean up all completed/failed jobs
  %(prog)s --job-id abc123     # Clean up specific job
  %(prog)s --job-id abc123 --force  # Force cleanup even if job is running""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        cleanup_parser.add_argument(
            "--job-id", metavar="JOB_ID", help="Clean up specific job (e.g., abc123)"
        )
        cleanup_parser.add_argument(
            "--all", action="store_true", help="Clean up all completed and failed jobs"
        )
        cleanup_parser.add_argument(
            "--force",
            action="store_true",
            help="Force cleanup even if job is running (stops container)",
        )

    def _add_kill_parser(self, subparsers):
        """Add kill command parser"""
        kill_parser = subparsers.add_parser(
            "kill",
            help="Kill running job immediately",
            description="Immediately stop a running job by killing its Docker container.",
            epilog="""Examples:
  %(prog)s abc123              # Kill running job abc123""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        kill_parser.add_argument(
            "job_id", metavar="JOB_ID", help="Job ID to kill (e.g., abc123)"
        )

    def _add_health_parser(self, subparsers):
        """Add health command parser"""
        health_parser = subparsers.add_parser(
            "health",
            help="Run system health checks",
            description="Validate system setup and Docker image compatibility before running jobs.",
            epilog="""Examples:
  %(prog)s --docker-image python:3.11              # Check Python base image
  %(prog)s --docker-image myproject:dev --spec task.md  # Check custom image + spec
  %(prog)s --docker-image python:3.11 --security  # Include security vulnerability scan
  %(prog)s --docker-image myproject:dev --ai --security  # Full health check with AI and security""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        health_parser.add_argument(
            "--docker-image",
            type=str,
            required=True,
            help="Docker image to health check (e.g., python:3.11, myproject:dev)",
        )
        health_parser.add_argument(
            "--spec", type=str, help="Optional spec file to validate for clarity"
        )
        health_parser.add_argument(
            "--ai",
            action="store_true",
            help="Use AI agent to analyze spec quality and provide detailed feedback",
        )
        health_parser.add_argument(
            "--security",
            action="store_true",
            help="Run Docker security vulnerability scan using Trivy",
        )
        health_parser.add_argument(
            "--language",
            choices=["python", "rust"],
            default="python",
            help="Project language for toolchain validation (default: python)",
        )

    def _add_update_parser(self, subparsers):
        """Add update-base-image command parser"""
        update_parser = subparsers.add_parser(
            "update-base-image",
            help="Build/update a Docker base image",
            description="Build or update a Docker base image using 'docker build -t <image> .'",
            epilog="""Examples:
  %(prog)s --image myproject:dev        # Build image 'myproject:dev' from current directory
  %(prog)s --image python-custom:latest # Build image 'python-custom:latest' from current directory""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        update_parser.add_argument(
            "--image",
            type=str,
            help="Docker image name to build (e.g., myproject:dev, python-custom:latest). Default from config.json.",
            default=self.config.get("default_base_image"),
        )
