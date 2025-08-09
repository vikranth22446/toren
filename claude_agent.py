#!/usr/bin/env python3
"""
Claude Agent Worker - Autonomous GitHub Issue/Spec Processor
"""

import argparse
import os
import sys
import subprocess
import json
import re
import fcntl
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import tempfile
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from job_manager import JobManager


class ClaudeAgent:
    def __init__(self, reviewer_username: str = "vikranth22446", max_lines: int = 400, warn_lines: int = 300):
        self.reviewer_username = reviewer_username
        self.max_lines = max_lines
        self.warn_lines = warn_lines
        self.job_manager = JobManager()
        
        # Security: Input validation patterns
        self.branch_name_pattern = re.compile(r'^[a-zA-Z0-9._/-]{1,100}$')
        self.docker_image_pattern = re.compile(r'^[a-z0-9._/-]+(?::[a-zA-Z0-9._-]+)?$')
        self.github_issue_pattern = re.compile(r'^https://github\.com/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+/issues/\d+$')
    
    def _sanitize_branch_name(self, branch_name: str) -> str:
        """Sanitize and validate branch name to prevent command injection"""
        if not branch_name:
            raise ValueError("Branch name cannot be empty")
        
        # Remove potentially dangerous characters
        branch_name = branch_name.strip()
        
        # Validate against allowlist pattern
        if not self.branch_name_pattern.match(branch_name):
            raise ValueError(f"Invalid branch name format: {branch_name}. Use only letters, numbers, dots, underscores, hyphens, and forward slashes.")
        
        # Additional security checks
        if any(char in branch_name for char in ['..', '~', '^', ':', '[', ']', '?', '*']):
            raise ValueError(f"Branch name contains forbidden characters: {branch_name}")
        
        if branch_name.startswith('-') or branch_name.endswith('-'):
            raise ValueError(f"Branch name cannot start or end with hyphen: {branch_name}")
            
        return branch_name
    
    def _sanitize_docker_image(self, image_name: str) -> str:
        """Sanitize and validate Docker image name to prevent command injection"""
        if not image_name:
            raise ValueError("Docker image name cannot be empty")
        
        # Remove potentially dangerous characters
        image_name = image_name.strip().lower()
        
        # Validate against allowlist pattern  
        if not self.docker_image_pattern.match(image_name):
            raise ValueError(f"Invalid Docker image format: {image_name}. Use format: name:tag or registry/name:tag")
        
        # Additional security checks
        if any(char in image_name for char in [';', '&', '|', '`', '$', '(', ')', '<', '>', '"', "'"]):
            raise ValueError(f"Docker image name contains forbidden characters: {image_name}")
        
        if len(image_name) > 200:
            raise ValueError(f"Docker image name too long (max 200 chars): {image_name}")
            
        return image_name
    
    def _sanitize_github_issue_url(self, issue_url: str) -> str:
        """Sanitize and validate GitHub issue URL to prevent command injection"""
        if not issue_url:
            raise ValueError("GitHub issue URL cannot be empty")
        
        # Remove potentially dangerous characters
        issue_url = issue_url.strip()
        
        # Validate against strict pattern
        if not self.github_issue_pattern.match(issue_url):
            raise ValueError(f"Invalid GitHub issue URL format: {issue_url}")
        
        # Additional security checks
        if len(issue_url) > 500:
            raise ValueError(f"GitHub issue URL too long: {issue_url}")
            
        return issue_url

    def _sanitize_pr_number(self, pr_number: str) -> str:
        """Sanitize and validate GitHub PR number"""
        if not pr_number:
            raise ValueError("PR number cannot be empty")
        
        pr_number = pr_number.strip()
        
        # Allow just numbers
        if pr_number.isdigit():
            if len(pr_number) > 10:  # Reasonable limit
                raise ValueError("PR number too long")
            return pr_number
        
        # Validate URL pattern for PR
        github_pr_pattern = r"^https://github\.com/[\w\-_.]+/[\w\-_.]+/pull/\d+$"
        if re.match(github_pr_pattern, pr_number):
            # Extract number from URL
            number = pr_number.split("/")[-1]
            if len(number) > 10:
                raise ValueError("PR number too long")
            return number
        
        raise ValueError(f"Invalid GitHub PR number or URL format: {pr_number}")
    
    def _validate_mount_path(self, path: Path, description: str) -> Path:
        """Validate and secure file paths for Docker mounts"""
        try:
            # Resolve to absolute path and check it exists
            resolved_path = path.resolve()
            
            # Security: Prevent path traversal attacks
            if not resolved_path.exists():
                raise ValueError(f"{description} does not exist: {resolved_path}")
            
            # Security: Ensure path is within safe directories
            safe_dirs = [
                Path.home(),  # User home directory
                Path.cwd(),   # Current working directory  
                Path("/tmp"),  # Temp directory
                Path("/var/tmp")  # Alternative temp directory
            ]
            
            # Allow if path is within any safe directory
            is_safe = False
            for safe_dir in safe_dirs:
                try:
                    resolved_safe_dir = safe_dir.resolve()
                    resolved_path.relative_to(resolved_safe_dir)
                    is_safe = True
                    break
                except ValueError:
                    continue
            
            if not is_safe:
                raise ValueError(f"{description} is outside safe directories: {resolved_path}")
            
            return resolved_path
            
        except Exception as e:
            raise ValueError(f"Invalid {description}: {e}")

    def _get_language_config(self, language: str) -> Dict[str, str]:
        """Get language-specific configuration and tools"""
        configs = {
            "python": {
                "security_tools": "bandit safety pip-audit",
                "test_command": "python -m pytest",
                "lint_command": "python -m flake8",
                "build_command": "python -m pip install -e .",
                "security_scan": "bandit -r . && safety check && pip-audit"
            },
            "rust": {
                "security_tools": "cargo-audit cargo-deny",
                "test_command": "cargo test",
                "lint_command": "cargo clippy -- -D warnings",
                "build_command": "cargo build",
                "security_scan": "cargo audit && cargo clippy && cargo deny check"
            }
        }
        return configs.get(language, configs["python"])

    def parse_args(self) -> argparse.Namespace:
        """Parse command line arguments"""
        parser = argparse.ArgumentParser(
            description="Claude Agent - Autonomous GitHub Agent",
            epilog="""Common workflows:
  Health check:   python3 claude_agent.py health --docker-image python:3.11 --security
  Start a job:    python3 claude_agent.py run --base-image python:3.11 --spec task.md --branch fix/auth-bug
  Check status:   python3 claude_agent.py status
  View logs:      python3 claude_agent.py logs abc123 --follow
  Clean up:       python3 claude_agent.py cleanup --all
  
  ML/AI with GPU:  python3 claude_agent.py run --base-image pytorch/pytorch:latest --spec ml_task.md --branch fix/training --env CUDA_VISIBLE_DEVICES=0 --volume /data:/workspace/data
  
Visit https://github.com/anthropics/claude-code for more information.""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # Run command (start new job)
        run_parser = subparsers.add_parser(
            "run",
            help="Start new agent job",
            description="Launch a Claude agent to work on GitHub issues or custom specifications.",
            epilog="""Examples:
  %(prog)s --base-image python:3.11 --spec task.md --branch fix/auth-bug
  %(prog)s --base-image myproject:dev --issue https://github.com/user/repo/issues/123 --branch fix/issue-123
  %(prog)s --base-image ubuntu:22.04 --spec task.md --branch feature/new-api --base-branch develop
  
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
            required=True,
            help="Branch name to create (e.g., fix/issue-123, feature/new-api)",
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
            required=True,
            help="Base Docker image to extend with agent tools (e.g., python:3.11, myproject:dev)",
        )
        run_parser.add_argument(
            "--base-branch",
            type=str,
            default="main",
            help="Base branch to branch from (default: main)",
        )
        run_parser.add_argument(
            "--disable-daemon",
            action="store_true",
            default=False,
            help="Disable background daemon mode and run synchronously",
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

        # Status command
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

        # Summary command
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

        # Logs command
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

        # Cleanup commands
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

        # Kill command
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
        
        # Health command
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
            "--docker-image", type=str, required=True,
            help="Docker image to health check (e.g., python:3.11, myproject:dev)"
        )
        health_parser.add_argument(
            "--spec", type=str,
            help="Optional spec file to validate for clarity"
        )
        health_parser.add_argument(
            "--ai", 
            action="store_true",
            help="Use AI agent to analyze spec quality and provide detailed feedback"
        )
        health_parser.add_argument(
            "--security",
            action="store_true", 
            help="Run Docker security vulnerability scan using Trivy"
        )
        health_parser.add_argument(
            "--language",
            choices=["python", "rust"],
            default="python",
            help="Project language for toolchain validation (default: python)",
        )

        args = parser.parse_args()

        # Default to 'run' if no command specified (backward compatibility)
        if args.command is None:
            # Parse as run command for backward compatibility
            parser = argparse.ArgumentParser(description="Claude Agent Worker")
            parser.add_argument("--spec", type=str, help="Path to markdown spec file")
            parser.add_argument("--issue", type=str, help="GitHub issue URL")
            parser.add_argument(
                "--branch", type=str, required=True, help="Branch name to create"
            )
            parser.add_argument(
                "--reviewer",
                type=str,
                default=self.reviewer_username,
                help="GitHub username to tag for review",
            )
            parser.add_argument(
                "--base-image",
                type=str,
                required=True,
                help="Base Docker image to extend with agent tools",
            )
            parser.add_argument(
                "--base-branch",
                type=str,
                default="main",
                help="Base branch to branch from (default: main)",
            )
            parser.add_argument(
                "--disable-daemon",
                action="store_true",
                default=False,
                help="Disable background daemon mode and run synchronously",
            )
            parser.add_argument(
                "--max-lines",
                type=int,
                default=400,
                help="Maximum lines changed allowed (default: 400)",
            )
            parser.add_argument(
                "--warn-lines", 
                type=int,
                default=300,
                help="Warning threshold for lines changed (default: 300)",
            )
            parser.add_argument(
                "--env",
                action="append",
                help="Environment variables to pass to container (e.g., --env CUDA_VISIBLE_DEVICES=0)",
            )
            parser.add_argument(
                "--volume",
                action="append",
                help="Additional volume mounts (e.g., --volume /host/models:/container/models)",
            )
            args = parser.parse_args()
            args.command = "run"

        return args

    def validate_inputs(self, args: argparse.Namespace) -> bool:
        """Validate input arguments with security sanitization"""
        try:
            input_count = sum(bool(x) for x in [args.spec, args.issue, args.pr])
            if input_count == 0:
                print("❌ Error: Must provide one of --spec, --issue, or --pr")
                return False
            elif input_count > 1:
                print("❌ Error: Can only specify one of --spec, --issue, or --pr at a time")
                return False

            if args.spec and not Path(args.spec).exists():
                print(f"❌ Error: Spec file not found: {args.spec}")
                return False

            # Security: Sanitize GitHub issue URL
            if args.issue:
                try:
                    args.issue = self._sanitize_github_issue_url(args.issue)
                except ValueError as e:
                    print(f"❌ Error: {e}")
                    return False

            # Security: Validate PR number
            if args.pr:
                try:
                    args.pr = self._sanitize_pr_number(args.pr)
                except ValueError as e:
                    print(f"❌ Error: {e}")
                    return False

            # Security: Sanitize branch name
            try:
                args.branch = self._sanitize_branch_name(args.branch)
            except ValueError as e:
                print(f"❌ Error: {e}")
                return False

            # Security: Sanitize base image name
            if not args.base_image:
                print("❌ Error: --base-image is required for security")
                return False
                
            try:
                args.base_image = self._sanitize_docker_image(args.base_image)
            except ValueError as e:
                print(f"❌ Error: {e}")
                return False

            return True
            
        except Exception as e:
            print(f"❌ Error during input validation: {e}")
            return False

    def read_spec_file(self, spec_path: str) -> str:
        """Read markdown specification file"""
        try:
            with open(spec_path, "r") as f:
                return f.read()
        except Exception as e:
            print(f"❌ Error reading spec file: {e}")
            return ""

    def fetch_issue_content(self, issue_url: str) -> Tuple[str, str]:
        """Fetch GitHub issue content using gh CLI"""
        try:
            issue_number = issue_url.split("/")[-1]
            result = subprocess.run(
                ["gh", "issue", "view", issue_number, "--json", "title,body"],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            return data.get("title", ""), data.get("body", "")
        except Exception as e:
            print(f"❌ Error fetching issue: {e}")
            return "", ""

    def fetch_pr_tasks(self, pr_number: str) -> str:
        """Fetch tasks for Claude from PR comments"""
        github_utils_path = Path(__file__).parent / "github_utils.py"
        
        try:
            result = subprocess.run([
                "python", str(github_utils_path), "extract-pr-tasks", pr_number
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                print(f"⚠️  Warning: Could not fetch PR tasks: {result.stderr}")
                return f"Unable to fetch tasks from PR #{pr_number}. Please check the PR exists and contains @claude mentions."
                
        except subprocess.TimeoutExpired:
            print("⚠️  Warning: Timeout fetching PR tasks")
            return f"Timeout fetching tasks from PR #{pr_number}"
        except Exception as e:
            print(f"⚠️  Warning: Error fetching PR tasks: {e}")
            return f"Error fetching tasks from PR #{pr_number}: {e}"

    def get_pr_details(self, pr_number: str) -> Optional[Dict[str, Any]]:
        """Get PR details using GitHub utils"""
        github_utils_path = Path(__file__).parent / "github_utils.py"
        
        try:
            result = subprocess.run([
                "python", str(github_utils_path), "get-pr", pr_number
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return json.loads(result.stdout.strip())
            else:
                print(f"⚠️  Warning: Could not fetch PR details: {result.stderr}")
                return None
                
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            print(f"⚠️  Warning: Error fetching PR details: {e}")
            return None

    def estimate_task_cost(self, task_content: str, language: str = "python") -> Optional[Dict[str, Any]]:
        """Use Claude to estimate potential API cost for a task"""
        try:
            import os
            if "ANTHROPIC_API_KEY" not in os.environ:
                print("❌ Cost estimation requires ANTHROPIC_API_KEY environment variable")
                return None
                
            print("💰 Asking Claude to estimate task cost...")
            
            estimation_prompt = f"""Analyze this task specification and estimate the Claude API cost to complete it:

TASK SPECIFICATION:
{task_content}

TARGET LANGUAGE: {language}

Please analyze and provide:
1. Task complexity (simple/medium/complex)
2. Estimated tokens needed (input + output)
3. Estimated cost in USD
4. Key factors affecting cost
5. Suggestions to reduce cost if applicable

Consider:
- Code analysis and understanding needed
- Amount of code to be written/modified
- Testing requirements
- Documentation needs
- Number of files likely to be read/modified

Respond with a JSON object in this format:
{{
    "complexity": "simple|medium|complex",
    "estimated_input_tokens": 1000,
    "estimated_output_tokens": 300,
    "estimated_total_cost": 0.0234,
    "cost_factors": ["factor1", "factor2"],
    "cost_reduction_tips": ["tip1", "tip2"],
    "confidence": "high|medium|low"
}}"""

            result = subprocess.run([
                "claude", "--print", estimation_prompt
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Try to extract JSON from response
                output = result.stdout.strip()
                
                # Look for JSON block in the response
                import json
                import re
                
                # Try to find JSON block
                json_match = re.search(r'\{[^}]+\}', output, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    estimate_data = json.loads(json_str)
                    
                    # Add metadata
                    estimate_data["language"] = language
                    estimate_data["model"] = "claude-3-5-sonnet"
                    estimate_data["raw_response"] = output
                    
                    return estimate_data
                else:
                    # Fallback to parsing response text
                    return {
                        "complexity": "unknown",
                        "estimated_total_cost": 0.02,  # Conservative fallback
                        "raw_response": output,
                        "language": language,
                        "model": "claude-3-5-sonnet",
                        "confidence": "low"
                    }
            else:
                print(f"⚠️  Warning: Claude estimation failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print("⚠️  Warning: Cost estimation timed out")
            return None
        except Exception as e:
            print(f"⚠️  Warning: Could not estimate cost: {e}")
            return None

    def print_cost_estimate(self, estimate: Dict[str, Any], task_type: str = "task") -> None:
        """Print formatted cost estimate"""
        if not estimate:
            print("❌ Cost estimation unavailable")
            return
            
        print(f"\n💰 **Claude's Cost Estimate for {task_type}**")
        print("-" * 50)
        
        if "complexity" in estimate:
            complexity_emoji = {"simple": "🟢", "medium": "🟡", "complex": "🔴"}.get(estimate["complexity"], "⚪")
            print(f"{complexity_emoji} Complexity: {estimate['complexity'].title()}")
        
        if "estimated_input_tokens" in estimate:
            print(f"🔤 Est. Input Tokens: {estimate['estimated_input_tokens']:,}")
        if "estimated_output_tokens" in estimate:
            print(f"📝 Est. Output Tokens: {estimate['estimated_output_tokens']:,}")
        
        if "estimated_total_cost" in estimate:
            print(f"💰 **Estimated Cost: ${estimate['estimated_total_cost']:.4f}**")
        
        if "confidence" in estimate:
            conf_emoji = {"high": "🎯", "medium": "📊", "low": "🤔"}.get(estimate["confidence"], "❓")
            print(f"{conf_emoji} Confidence: {estimate['confidence'].title()}")
            
        print(f"🤖 Model: {estimate.get('model', 'claude-3-5-sonnet')}")
        print(f"🔧 Language: {estimate.get('language', 'unknown')}")
        
        if "cost_factors" in estimate and estimate["cost_factors"]:
            print(f"\n📋 **Cost Factors:**")
            for factor in estimate["cost_factors"]:
                print(f"  • {factor}")
                
        if "cost_reduction_tips" in estimate and estimate["cost_reduction_tips"]:
            print(f"\n💡 **Cost Reduction Tips:**")
            for tip in estimate["cost_reduction_tips"]:
                print(f"  • {tip}")
        
        # Show raw response if available (for debugging)
        if estimate.get("confidence") == "low" and "raw_response" in estimate:
            print(f"\n🔍 **Raw Analysis:**")
            print(estimate["raw_response"][:300] + "..." if len(estimate["raw_response"]) > 300 else estimate["raw_response"])
            
        print()

    def validate_spec_safety(self, content: str) -> List[str]:
        """Check for privacy/security concerns in spec"""
        concerns = []

        # Privacy/security keywords
        danger_patterns = [
            r"\bpassword\b",
            r"\bapi[_\s]?key\b",
            r"\bsecret\b",
            r"\btoken\b",
            r"\bcredential\b",
            r"\bprivate[_\s]?key\b",
            r"\bhardcode\b",
            r"\bexpose\b.*\b(database|db)\b",
            r"\bpublic\b.*\b(sensitive|private)\b",
        ]

        for pattern in danger_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                concerns.append(f"Potential security/privacy issue: {pattern}")

        # Architecture concerns
        if len(content.split("\n")) > 100:
            concerns.append("Spec is very large - may result in oversized PR")

        return concerns

    def merge_specifications(
        self, spec_content: str, issue_title: str, issue_body: str
    ) -> str:
        """Combine spec file and issue into unified task description"""
        merged = []

        if issue_title and issue_body:
            merged.append(f"## GitHub Issue: {issue_title}\n{issue_body}")

        if spec_content:
            merged.append(f"## Specification\n{spec_content}")

        merged.append(f"""
## PR Guidelines
- Keep changes under {self.max_lines} lines (warn at {self.warn_lines})
- Follow existing codebase style and patterns
- Avoid excessive comments and tests
- Prefer simple, straightforward solutions
- Don't over-engineer
- Follow the specification precisely unless safety concerns arise
""")

        return "\n\n".join(merged)

    def generate_agent_dockerfile(self, base_image: str) -> str:
        """Generate Dockerfile extending base image with agent tools"""
        return f"""FROM {base_image}

# Update package manager and install basic tools
RUN if command -v apt-get >/dev/null 2>&1; then \\
        apt-get update && apt-get install -y curl git ca-certificates; \\
    elif command -v apk >/dev/null 2>&1; then \\
        apk add --no-cache curl git ca-certificates bash; \\
    elif command -v yum >/dev/null 2>&1; then \\
        yum update -y && yum install -y curl git ca-certificates; \\
    fi

# Install GitHub CLI
RUN if command -v apt-get >/dev/null 2>&1; then \\
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \\
        echo "deb [arch=$$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list && \\
        apt-get update && apt-get install -y gh; \\
    else \\
        curl -fsSL https://github.com/cli/cli/releases/download/v2.40.1/gh_2.40.1_linux_amd64.tar.gz | \\
        tar -xz -C /tmp && \\
        mv /tmp/gh_2.40.1_linux_amd64/bin/gh /usr/local/bin/gh && \\
        rm -rf /tmp/gh_2.40.1_linux_amd64; \\
    fi

# Install Claude Code CLI
RUN curl -fsSL https://claude.ai/install.sh | sh

# Install Python security scanning tools (optional)
COPY security-requirements.txt /tmp/security-requirements.txt
RUN if command -v pip >/dev/null 2>&1; then \\
        pip install -r /tmp/security-requirements.txt || echo "Warning: Failed to install security tools"; \\
    elif command -v pip3 >/dev/null 2>&1; then \\
        pip3 install -r /tmp/security-requirements.txt || echo "Warning: Failed to install security tools"; \\
    fi && \\
    rm /tmp/security-requirements.txt

# Add security scanning utility script
RUN echo '#!/bin/bash' > /usr/local/bin/claude-security-scan && \\
    echo 'echo "🔍 Claude Agent Security Scanner"' >> /usr/local/bin/claude-security-scan && \\
    echo 'echo "Available tools:"' >> /usr/local/bin/claude-security-scan && \\
    echo 'command -v bandit >/dev/null && echo "  ✅ bandit - Python security scanner"' >> /usr/local/bin/claude-security-scan && \\
    echo 'command -v safety >/dev/null && echo "  ✅ safety - Dependency vulnerability scanner"' >> /usr/local/bin/claude-security-scan && \\
    echo 'command -v semgrep >/dev/null && echo "  ✅ semgrep - Static analysis security scanner"' >> /usr/local/bin/claude-security-scan && \\
    echo 'echo ""' >> /usr/local/bin/claude-security-scan && \\
    echo 'if [ "$1" = "scan" ]; then' >> /usr/local/bin/claude-security-scan && \\
    echo '    echo "Running bandit security scan on Python files..."' >> /usr/local/bin/claude-security-scan && \\
    echo '    find /workspace -name "*.py" -exec bandit -ll {{}} + 2>/dev/null || echo "No Python files found or bandit failed"' >> /usr/local/bin/claude-security-scan && \\
    echo 'else' >> /usr/local/bin/claude-security-scan && \\
    echo '    echo "Usage: claude-security-scan scan"' >> /usr/local/bin/claude-security-scan && \\
    echo 'fi' >> /usr/local/bin/claude-security-scan && \\
    chmod +x /usr/local/bin/claude-security-scan

# Ensure PATH includes Claude Code
ENV PATH="/root/.local/bin:$PATH"

# Copy container entrypoint script
COPY container_entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
"""

    @contextmanager
    def _docker_build_lock(self, agent_image: str):
        """Context manager for Docker build operations to prevent race conditions"""
        lock_file = Path.home() / ".claude_agent" / "build_locks" / f"{agent_image.replace(':', '_').replace('/', '_')}.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(lock_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
                yield
        finally:
            try:
                lock_file.unlink(missing_ok=True)
            except OSError:
                pass

    def build_agent_image(self, base_image: str) -> str:
        """Build derived image with agent tools, return image name"""
        # Generate unique tag based on base image
        image_hash = hashlib.md5(base_image.encode()).hexdigest()[:8]
        agent_image = f"claude-agent-{image_hash}:latest"

        print(f"🔨 Building agent image from {base_image}...")

        try:
            # Use exclusive locking to prevent concurrent builds of same image
            with self._docker_build_lock(agent_image):
                # Double-check image existence after acquiring lock
                result = subprocess.run(
                    ["docker", "images", "-q", agent_image], capture_output=True, text=True
                )

                if result.stdout.strip():
                    print(f"✅ Using cached agent image: {agent_image}")
                    return agent_image
                
                print(f"🔄 Building new agent image: {agent_image}")

                # Generate Dockerfile
                dockerfile_content = self.generate_agent_dockerfile(base_image)

                # Create temporary build context
                with tempfile.TemporaryDirectory() as temp_dir:
                    dockerfile_path = Path(temp_dir) / "Dockerfile"
                    with open(dockerfile_path, "w") as f:
                        f.write(dockerfile_content)

                    # Copy entrypoint script to build context
                    entrypoint_src = Path(__file__).parent / "container_entrypoint.sh"
                    entrypoint_dst = Path(temp_dir) / "container_entrypoint.sh"
                    if entrypoint_src.exists():
                        with open(entrypoint_src, "r") as src, open(
                            entrypoint_dst, "w"
                        ) as dst:
                            dst.write(src.read())
                    
                    # Copy security requirements to build context
                    security_req_src = Path(__file__).parent / "security-requirements.txt"
                    security_req_dst = Path(temp_dir) / "security-requirements.txt"
                    if security_req_src.exists():
                        with open(security_req_src, "r") as src, open(
                            security_req_dst, "w"
                        ) as dst:
                            dst.write(src.read())
                    else:
                        # Create minimal security requirements if file doesn't exist
                        with open(security_req_dst, "w") as f:
                            f.write("# Security tools for Claude Agent\nbandit>=1.7.0\n")

                    # Build image
                    result = subprocess.run(
                        [
                            "docker",
                            "build",
                            "-t",
                            agent_image,
                            "-f",
                            str(dockerfile_path),
                            ".",
                        ],
                        cwd=temp_dir,
                        capture_output=True,
                        text=True,
                    )

                    if result.returncode != 0:
                        print(f"❌ Docker build failed: {result.stderr}")
                        return None

                    print(f"✅ Built agent image: {agent_image}")
                    return agent_image

        except Exception as e:
            print(f"❌ Error building agent image: {e}")
            return None

    def execute_in_container(
        self,
        image: str,
        task_spec: str,
        branch_name: str,
        base_branch: str,
        issue_number: Optional[str] = None,
        reviewer: Optional[str] = None,
        custom_env: Optional[List[str]] = None,
        custom_volumes: Optional[List[str]] = None,
        language: str = "python",
    ) -> bool:
        """Execute Claude Code inside Docker container with GitHub utilities"""
        try:
            print(f"⚙️ Executing Claude Code in container: {image}")

            # Write task spec to temporary file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(task_spec)
                spec_file = f.name

            # Get path to github_utils.py
            github_utils_path = Path(__file__).parent / "github_utils.py"

            # Prepare Docker command with mounted credentials and utilities
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "-v",
                spec_file + ":/tmp/task_spec.md",  # Mount task spec
                "-v",
                f"{github_utils_path}:/usr/local/bin/github_utils.py",  # Mount GitHub utilities
                "-w",
                "/workspace",  # Set working directory (provided by base container)
            ]

            # Security: Mount git credentials with path validation
            try:
                gitconfig_path = Path.home() / ".gitconfig"
                if gitconfig_path.exists():
                    validated_path = self._validate_mount_path(gitconfig_path, "Git config")
                    docker_cmd.extend(["-v", f"{validated_path}:/root/.gitconfig"])
                
                ssh_path = Path.home() / ".ssh"
                if ssh_path.exists():
                    validated_path = self._validate_mount_path(ssh_path, "SSH directory")
                    docker_cmd.extend(["-v", f"{validated_path}:/root/.ssh"])
                
                gh_config_path = Path.home() / ".config/gh"
                if gh_config_path.exists():
                    validated_path = self._validate_mount_path(gh_config_path, "GitHub CLI config")
                    docker_cmd.extend(["-v", f"{validated_path}:/root/.config/gh"])
                    
            except ValueError as e:
                print(f"⚠️  Warning: Skipping credential mount: {e}")
                # Continue without these credentials rather than failing

            # Process custom volumes with security validation
            if custom_volumes:
                for volume_spec in custom_volumes:
                    try:
                        # Parse volume specification: "host_path:container_path" or "host_path:container_path:options"
                        parts = volume_spec.split(":")
                        if len(parts) < 2:
                            print(f"⚠️  Warning: Invalid volume specification: {volume_spec}")
                            continue
                        
                        host_path = parts[0]
                        container_path = parts[1]
                        options = parts[2] if len(parts) > 2 else ""
                        
                        # Validate host path exists and is accessible
                        host_path_obj = Path(host_path)
                        if not host_path_obj.exists():
                            print(f"⚠️  Warning: Host path does not exist: {host_path}")
                            continue
                        
                        # Security validation for host paths
                        validated_host_path = self._validate_mount_path(host_path_obj, f"Custom volume {host_path}")
                        
                        # Build volume mount string
                        volume_mount = f"{validated_host_path}:{container_path}"
                        if options:
                            volume_mount += f":{options}"
                        
                        docker_cmd.extend(["-v", volume_mount])
                        print(f"  📁 Added volume mount: {host_path} -> {container_path}")
                        
                    except (ValueError, IndexError) as e:
                        print(f"⚠️  Warning: Skipping invalid volume mount {volume_spec}: {e}")
                        continue

            # Add environment variables (secure credential handling)
            env_vars = []
            api_key_file = None
            if "ANTHROPIC_API_KEY" in os.environ:
                # Write API key to temporary file for secure mounting
                api_key_fd, api_key_path = tempfile.mkstemp(suffix=".key", prefix="anthropic_")
                try:
                    with os.fdopen(api_key_fd, 'w') as f:
                        f.write(os.environ['ANTHROPIC_API_KEY'])
                    api_key_file = api_key_path
                    # Mount API key as file instead of environment variable
                    docker_cmd.extend(["-v", f"{api_key_path}:/run/secrets/anthropic_api_key:ro"])
                    # Set environment variable to point to the mounted file
                    env_vars.extend(["-e", "ANTHROPIC_API_KEY_FILE=/run/secrets/anthropic_api_key"])
                except Exception as e:
                    print(f"⚠️  Warning: Could not create secure API key file: {e}")
                    # Fallback to environment variable (less secure)
                    env_vars.extend(["-e", f"ANTHROPIC_API_KEY={os.environ['ANTHROPIC_API_KEY']}"]) 
                    if api_key_file:
                        try:
                            os.unlink(api_key_file)
                        except OSError:
                            pass
                        api_key_file = None
            if issue_number:
                env_vars.extend(["-e", f"GITHUB_ISSUE_NUMBER={issue_number}"])

            # Add git environment variables for the entrypoint script
            env_vars.extend(["-e", f"BASE_BRANCH={base_branch}"])
            env_vars.extend(["-e", f"BRANCH_NAME={branch_name}"])
            env_vars.extend(["-e", "TASK_SPEC_FILE=/tmp/task_spec.md"])
            env_vars.extend(["-e", f"LANGUAGE={language}"])
            if reviewer:
                env_vars.extend(["-e", f"DEFAULT_REVIEWER={reviewer}"])
            
            # Process custom environment variables
            if custom_env:
                for env_spec in custom_env:
                    try:
                        # Parse environment variable: "KEY=value"
                        if "=" not in env_spec:
                            print(f"⚠️  Warning: Invalid environment variable specification: {env_spec}")
                            continue
                        
                        key, value = env_spec.split("=", 1)
                        
                        # Basic validation of environment variable key
                        if not key or not key.replace("_", "").replace("-", "").isalnum():
                            print(f"⚠️  Warning: Invalid environment variable key: {key}")
                            continue
                        
                        env_vars.extend(["-e", f"{key}={value}"])
                        print(f"  🔧 Added environment variable: {key}")
                        
                    except ValueError as e:
                        print(f"⚠️  Warning: Skipping invalid environment variable {env_spec}: {e}")
                        continue

            docker_cmd.extend(env_vars)

            # Note: Container entrypoint handles git operations and Claude Code execution
            # No need to pass complex prompts - the entrypoint script manages everything
            docker_cmd.append(image)

            # Execute container
            result = subprocess.run(docker_cmd, capture_output=True, text=True)

            # Cleanup temporary files
            Path(spec_file).unlink()
            if api_key_file:
                try:
                    os.unlink(api_key_file)
                except OSError:
                    pass

            if result.returncode == 0:
                print("✅ Container execution completed")
                return True
            else:
                print(f"❌ Container execution failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Error executing container: {e}")
            # Cleanup temp files on exception
            if 'spec_file' in locals():
                Path(spec_file).unlink(missing_ok=True)
            if 'api_key_file' in locals() and api_key_file:
                try:
                    os.unlink(api_key_file)
                except OSError:
                    pass
            return False

    def create_branch(self, branch_name: str) -> bool:
        """Create and checkout new branch"""
        try:
            subprocess.run(
                ["git", "checkout", "-b", branch_name], check=True, capture_output=True
            )
            print(f"✅ Created branch: {branch_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create branch: {e}")
            return False

    def post_github_comment(
        self,
        message: str,
        issue_number: Optional[str] = None,
        pr_number: Optional[str] = None,
    ) -> bool:
        """Post comment to GitHub issue or PR"""
        try:
            if issue_number:
                subprocess.run(
                    ["gh", "issue", "comment", issue_number, "--body", message],
                    check=True,
                )
            elif pr_number:
                subprocess.run(
                    ["gh", "pr", "comment", pr_number, "--body", message], check=True
                )
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to post comment: {e}")
            return False

    def execute_claude_code(
        self,
        task_spec: str,
        base_image: str,
        branch_name: str,
        base_branch: str,
        issue_number: Optional[str] = None,
        custom_env: Optional[List[str]] = None,
        custom_volumes: Optional[List[str]] = None,
        language: str = "python",
        reviewer: Optional[str] = None,
    ) -> bool:
        """Execute Claude Code with the task specification in Docker container"""
        # Build and use containerized execution only
        agent_image = self.build_agent_image(base_image)
        if not agent_image:
            return False
        return self.execute_in_container(
            agent_image, task_spec, branch_name, base_branch, issue_number, reviewer, custom_env, custom_volumes, language
        )

    def validate_changes(self) -> Tuple[bool, List[str], int]:
        """Validate the changes made by Claude Code"""
        issues = []

        try:
            # Count lines changed
            result = subprocess.run(
                ["git", "diff", "--stat", "HEAD~1"], capture_output=True, text=True
            )
            lines_changed = self._count_lines_from_stat(result.stdout)

            if lines_changed > self.max_lines:
                issues.append(
                    f"Too many lines changed: {lines_changed} (max: {self.max_lines})"
                )
            elif lines_changed > self.warn_lines:
                issues.append(f"Warning: Large changeset: {lines_changed} lines")

            # Check for uncommitted changes
            result = subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True
            )
            if not result.stdout.strip():
                issues.append("No changes detected")

            return (
                len(issues) == 0 or all("Warning:" in issue for issue in issues),
                issues,
                lines_changed,
            )

        except Exception as e:
            return False, [f"Validation error: {e}"], 0

    def _count_lines_from_stat(self, stat_output: str) -> int:
        """Extract line count from git diff --stat output"""
        try:
            for line in stat_output.split("\n"):
                if "insertions" in line or "deletions" in line:
                    numbers = re.findall(r"\d+", line)
                    return sum(int(n) for n in numbers[:2])  # insertions + deletions
        except:
            pass
        return 0

    def commit_and_push(self, branch_name: str, task_summary: str) -> bool:
        """Commit changes and push to remote"""
        try:
            # Add all changes
            subprocess.run(["git", "add", "."], check=True)

            # Commit with message
            commit_msg = f"""Auto-fix: {task_summary[:50]}

{task_summary}

🤖 Generated with Claude Agent
"""
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)

            # Push branch
            subprocess.run(["git", "push", "-u", "origin", branch_name], check=True)
            print(f"✅ Committed and pushed branch: {branch_name}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to commit/push: {e}")
            return False

    def create_pull_request(
        self, branch_name: str, title: str, body: str
    ) -> Optional[str]:
        """Create pull request and return PR number"""
        try:
            result = subprocess.run(
                ["gh", "pr", "create", "--title", title, "--body", body],
                capture_output=True,
                text=True,
                check=True,
            )

            # Extract PR number from URL
            pr_url = result.stdout.strip()
            pr_number = pr_url.split("/")[-1]
            print(f"✅ Created PR: {pr_url}")
            return pr_number

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create PR: {e}")
            return None

    def generate_pr_body(self, task_spec: str, lines_changed: int) -> str:
        """Generate PR description"""
        return f"""## 📋 Task Summary

{task_spec[:500]}{"..." if len(task_spec) > 500 else ""}

## 📊 Changes
- **Lines changed**: {lines_changed}
- **Branch**: Automated fix by Claude Agent

## 🧪 Testing
Please review the changes and test as appropriate for your workflow.

🤖 Generated with Claude Agent"""

    def run(self) -> None:
        """Main execution flow"""
        args = self.parse_args()

        # Route to appropriate command handler
        if args.command == "run":
            self.run_job_command(args)
        elif args.command == "status":
            self.show_status(args.job_id, args.filter)
        elif args.command == "summary":
            self.show_summary(args.job_id)
        elif args.command == "logs":
            self.show_logs(args.job_id, args.follow)
        elif args.command == "cleanup":
            self.cleanup_jobs(args.job_id, args.all, args.force)
        elif args.command == "kill":
            self.kill_job(args.job_id)
        elif args.command == "health":
            self.run_health_check(args.docker_image, args.spec, args.ai, args.security, args.language)
        else:
            print("❌ Unknown command")
            sys.exit(1)

    def run_job_command(self, args: argparse.Namespace) -> None:
        """Handle the run command"""
        if not self.validate_inputs(args):
            sys.exit(1)

        # Handle daemon mode (default True, unless --disable-daemon is used)
        if not args.disable_daemon:
            return self.run_daemon_mode(args)

        print("🤖 Claude Agent starting...")
        print(f"Branch: {args.branch}")
        print(f"Reviewer: {args.reviewer}")

        # Read inputs
        spec_content = ""
        issue_title = ""
        issue_body = ""
        issue_number = None

        if args.spec:
            spec_content = self.read_spec_file(args.spec)

        if args.issue:
            issue_title, issue_body = self.fetch_issue_content(args.issue)
            issue_number = args.issue.split("/")[-1]

        if args.pr:
            # Extract task specification from PR comments
            pr_task_spec = self.fetch_pr_tasks(args.pr)
            # Get PR details to determine branch
            pr_data = self.get_pr_details(args.pr)
            if pr_data and pr_data.get('headRefName'):
                args.branch = pr_data['headRefName']  # Use existing PR branch
                print(f"📋 Using existing PR branch: {args.branch}")
            # Store PR number for container environment
            self._current_pr_number = args.pr
            # For PR mode, the task spec comes entirely from PR analysis
            all_content = pr_task_spec
        else:
            # For issue/spec mode, merge the specifications
            all_content = f"{spec_content}\n{issue_body}"

        # Handle cost estimation if requested
        if args.cost_estimate:
            task_type = "PR continuation" if args.pr else "new task"
            estimate = self.estimate_task_cost(all_content, args.language)
            self.print_cost_estimate(estimate, task_type)
            
            # Ask user if they want to proceed
            if estimate and estimate.get("estimated_total_cost", 0) > 0.10:  # Alert for costs > $0.10
                response = input("💰 Estimated cost is significant. Continue? [y/N]: ").lower()
                if response != 'y':
                    print("⏹️  Task cancelled by user")
                    sys.exit(0)
            elif estimate:
                response = input("💰 Proceed with execution? [Y/n]: ").lower()
                if response == 'n':
                    print("⏹️  Task cancelled by user")
                    sys.exit(0)
            
            print("🚀 Proceeding with task execution...\n")

        # Validate safety
        safety_concerns = self.validate_spec_safety(all_content)

        if safety_concerns:
            concern_msg = f"""❌ **BLOCKED - Safety Review Required** @{args.reviewer}

**Issues Found**:
{chr(10).join(f"• {concern}" for concern in safety_concerns)}

**Recommendation**: Manual review required before proceeding.

🚫 Claude Agent execution halted."""

            if issue_number:
                self.post_github_comment(concern_msg, issue_number=issue_number)
            print(concern_msg)
            sys.exit(1)

        # Merge specifications
        task_spec = self.merge_specifications(spec_content, issue_title, issue_body)

        # Branch creation happens in container

        # Post initial comment
        if issue_number:
            start_msg = f"""🤖 **Claude Agent Started**

Working on branch: `{args.branch}`

**Task**: {issue_title or "Custom specification"}
**Estimated scope**: {len(task_spec.split())} words

⚙️ Processing..."""
            self.post_github_comment(start_msg, issue_number=issue_number)

        # Execute Claude Code
        if not self.execute_claude_code(
            task_spec, args.base_image, args.branch, args.base_branch, issue_number, args.env, args.volume, args.language, args.reviewer
        ):
            error_msg = f"""❌ **Claude Agent Failed** @{args.reviewer}

**Issue**: Claude Code execution failed
**Branch**: `{args.branch}`

Manual intervention required."""

            if issue_number:
                self.post_github_comment(error_msg, issue_number=issue_number)
            sys.exit(1)

        # Validate changes
        is_valid, issues, lines_changed = self.validate_changes()

        if not is_valid:
            error_msg = f"""❌ **Claude Agent Validation Failed** @{args.reviewer}

**Issues**:
{chr(10).join(f"• {issue}" for issue in issues)}

**Branch**: `{args.branch}`
**Lines changed**: {lines_changed}

Manual review required."""

            if issue_number:
                self.post_github_comment(error_msg, issue_number=issue_number)
            sys.exit(1)

        # Commit and push
        task_summary = issue_title or "Custom task from specification"
        if not self.commit_and_push(args.branch, task_summary):
            sys.exit(1)

        # Create PR
        pr_title = f"Fix: {task_summary}"
        pr_body = self.generate_pr_body(task_spec, lines_changed)
        pr_number = self.create_pull_request(args.branch, pr_title, pr_body)

        if not pr_number:
            sys.exit(1)

        # Get cost information for the comment
        cost_info = self._get_session_cost_info()
        cost_section = ""
        if cost_info:
            cost_lines = []
            if cost_info.get("total_cost", 0) > 0:
                cost_lines.append(f"💰 **Cost**: ${cost_info['total_cost']:.4f}")
            if cost_info.get("total_tokens", 0) > 0:
                cost_lines.append(f"🔤 **Tokens**: {cost_info['total_tokens']:,}")
            if cost_lines:
                cost_section = "\n" + "\n".join(cost_lines)

        # Post completion comment
        success_msg = f"""✅ **Task Completed** @{args.reviewer}

**PR Created**: #{pr_number}
**Branch**: `{args.branch}`
**Lines changed**: {lines_changed}{cost_section}

Ready for review! 🎉"""

        if issue_number:
            self.post_github_comment(success_msg, issue_number=issue_number)

        print("🎉 Claude Agent completed successfully!")

    def _get_session_cost_info(self) -> Optional[Dict[str, Any]]:
        """Get cost information for the current session"""
        try:
            import subprocess
            import json
            
            # Query Claude for cost information
            result = subprocess.run([
                "claude", "--print", "--output-format", "json", "/cost"
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                cost_data = json.loads(result.stdout)
                return {
                    "total_cost": cost_data.get("total_cost", 0.0),
                    "input_tokens": cost_data.get("input_tokens", 0),
                    "output_tokens": cost_data.get("output_tokens", 0),
                    "total_tokens": cost_data.get("input_tokens", 0) + cost_data.get("output_tokens", 0)
                }
        except Exception:
            pass  # Silently fail if cost info not available
        
        return None

    # Dashboard methods
    def format_timestamp(self, iso_string: str) -> str:
        """Format ISO timestamp for display"""
        try:
            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            diff = now - dt

            if diff.days > 0:
                return f"{diff.days}d ago"
            elif diff.seconds > 3600:
                return f"{diff.seconds // 3600}h ago"
            elif diff.seconds > 60:
                return f"{diff.seconds // 60}m ago"
            else:
                return "just now"
        except:
            return iso_string

    def status_color(self, status: str) -> str:
        """Get color code for status"""
        colors = {
            "running": "\033[94m",  # Blue
            "completed": "\033[92m",  # Green
            "failed": "\033[91m",  # Red
            "queued": "\033[93m",  # Yellow
            "cancelled": "\033[90m",  # Gray
        }
        reset = "\033[0m"
        return colors.get(status, "") + status + reset

    def show_status(self, job_id: str = None, status_filter: str = None) -> None:
        """Show job status"""
        if job_id:
            # Show detailed status for specific job
            job = self.job_manager.get_job(job_id)
            if not job:
                print(f"❌ Job {job_id} not found")
                sys.exit(1)

            self._show_detailed_job(job)
        else:
            # Show summary of all jobs
            jobs = self.job_manager.list_jobs(status_filter)
            if not jobs:
                print("No jobs found")
                return

            self._show_job_list(jobs)

    def _show_job_list(self, jobs: List[Dict]) -> None:
        """Show compact job list with cost information"""
        print(
            f"{'JOB ID':<10} {'STATUS':<12} {'BRANCH':<18} {'COST':<8} {'LINES':<8} {'CREATED':<10} {'SUMMARY'}"
        )
        print("-" * 90)

        for job in jobs:
            job_id = job["job_id"]
            status = self.status_color(job["status"])
            branch = (
                job["branch_name"][:16] + ".."
                if len(job["branch_name"]) > 18
                else job["branch_name"]
            )
            
            # Format cost and lines changed
            cost_info = job.get("cost_info", {})
            git_stats = job.get("git_stats", {})
            cost_str = f"${cost_info.get('total_cost', 0):.3f}" if cost_info.get('total_cost', 0) > 0 else "-"
            lines_str = str(git_stats.get('total_lines_changed', 0)) if git_stats.get('total_lines_changed', 0) > 0 else "-"
            
            created = self.format_timestamp(job["created_at"])
            summary = (
                job["ai_summary"][:35] + "..."
                if len(job["ai_summary"]) > 35
                else job["ai_summary"]
            )

            print(f"{job_id:<10} {status:<20} {branch:<18} {cost_str:<8} {lines_str:<8} {created:<10} {summary}")

    def _show_detailed_job(self, job: Dict) -> None:
        """Show detailed job information"""
        print(f"🤖 Job Details: {job['job_id']}")
        print(f"Status: {self.status_color(job['status'])}")
        print(f"Branch: {job['branch_name']} (from {job['base_branch']})")
        print(f"Base Image: {job['base_image']}")
        print(f"Created: {job['created_at']}")
        print(f"Updated: {job['updated_at']}")

        if job.get("github_issue"):
            print(f"GitHub Issue: {job['github_issue']}")

        if job.get("pr_url"):
            print(f"Pull Request: {job['pr_url']}")

        if job.get("container_id"):
            print(f"Container: {job['container_id']}")

        if job.get("error_message"):
            print(f"❌ Error: {job['error_message']}")

        # Show cost and git statistics if available
        cost_info = job.get("cost_info", {})
        git_stats = job.get("git_stats", {})
        
        if cost_info.get("total_cost", 0) > 0 or git_stats.get("total_lines_changed", 0) > 0:
            print(f"\n💰 Session Metrics:")
            if cost_info.get("total_cost", 0) > 0:
                print(f"  Cost: ${cost_info.get('total_cost', 0):.4f}")
                total_tokens = cost_info.get('input_tokens', 0) + cost_info.get('output_tokens', 0)
                if total_tokens > 0:
                    print(f"  Tokens: {total_tokens:,} ({cost_info.get('input_tokens', 0):,} input + {cost_info.get('output_tokens', 0):,} output)")
                if cost_info.get('session_duration', 0) > 0:
                    duration_min = cost_info.get('session_duration', 0) // 60
                    duration_sec = cost_info.get('session_duration', 0) % 60
                    print(f"  Duration: {duration_min}m {duration_sec}s")
            
            if git_stats.get("total_lines_changed", 0) > 0:
                print(f"  Lines changed: +{git_stats.get('lines_added', 0)} -{git_stats.get('lines_deleted', 0)} (total: {git_stats.get('total_lines_changed', 0)})")
                print(f"  Files modified: {git_stats.get('files_changed', 0)}")

        print(f"\n📋 Task Summary:")
        print(f"  {job['ai_summary']}")

        if job.get("progress_log"):
            print(f"\n📈 Progress Log:")
            for entry in job["progress_log"][-5:]:  # Show last 5 entries
                timestamp = self.format_timestamp(entry["timestamp"])
                print(f"  [{timestamp}] {entry['message']}")

        print(f"\n📄 Task Specification:")
        task_lines = job["task_spec"].split("\n")
        for line in task_lines[:10]:  # Show first 10 lines
            print(f"  {line}")
        if len(task_lines) > 10:
            print(f"  ... ({len(task_lines) - 10} more lines)")

    def show_summary(self, job_id: str) -> None:
        """Show AI-generated task summary"""
        job = self.job_manager.get_job(job_id)
        if not job:
            print(f"❌ Job {job_id} not found")
            sys.exit(1)

        print(f"🎯 AI Summary for Job {job_id}:")
        print(f"Status: {self.status_color(job['status'])}")
        print(f"Branch: {job['branch_name']}")
        print()
        print(job["ai_summary"])

        if job.get("progress_log"):
            print(f"\n🔄 Latest Progress:")
            latest = job["progress_log"][-1]
            print(
                f"  [{self.format_timestamp(latest['timestamp'])}] {latest['message']}"
            )

    def show_logs(self, job_id: str, follow: bool = False) -> None:
        """Show job logs"""
        job = self.job_manager.get_job(job_id)
        if not job:
            print(f"❌ Job {job_id} not found")
            sys.exit(1)

        if not job.get("container_id"):
            print(f"❌ No container found for job {job_id}")
            sys.exit(1)

        print(f"📋 Logs for Job {job_id} (Container: {job['container_id']}):")
        print("-" * 60)

        if follow:
            # Follow logs in real-time
            try:
                subprocess.run(["docker", "logs", "-f", job["container_id"]])
            except KeyboardInterrupt:
                print("\n👋 Log following stopped")
        else:
            # Show current logs
            logs = self.job_manager.get_container_logs(job_id)
            if logs:
                print(logs)
            else:
                print("No logs available")

    def cleanup_jobs(
        self, job_id: str = None, cleanup_all: bool = False, force: bool = False
    ) -> None:
        """Clean up jobs"""
        if cleanup_all:
            count = self.job_manager.cleanup_completed_jobs()
            print(f"✅ Cleaned up {count} completed jobs")
        elif job_id:
            job = self.job_manager.get_job(job_id)
            if not job:
                print(f"❌ Job {job_id} not found")
                sys.exit(1)

            if job["status"] in ["running", "queued"] and not force:
                print(
                    f"⚠️  Job {job_id} is {job['status']}. Use --force to cleanup running jobs"
                )
                sys.exit(1)

            if self.job_manager.cleanup_job(job_id):
                print(f"✅ Cleaned up job {job_id}")
            else:
                print(f"❌ Failed to cleanup job {job_id}")
        else:
            print("❌ Must specify --job-id or --all")
            sys.exit(1)

    def kill_job(self, job_id: str) -> None:
        """Kill running job"""
        job = self.job_manager.get_job(job_id)
        if not job:
            print(f"❌ Job {job_id} not found")
            sys.exit(1)

        if job["status"] not in ["running", "queued"]:
            print(f"❌ Job {job_id} is not running (status: {job['status']})")
            sys.exit(1)

        if job.get("container_id"):
            try:
                subprocess.run(
                    ["docker", "kill", job["container_id"]],
                    check=True,
                    capture_output=True,
                )
                self.job_manager.update_job_status(job_id, "cancelled")
                print(f"✅ Killed job {job_id}")
            except subprocess.CalledProcessError:
                print(f"❌ Failed to kill container for job {job_id}")
                sys.exit(1)
        else:
            self.job_manager.update_job_status(job_id, "cancelled")
            print(f"✅ Cancelled job {job_id}")

    def run_health_check(self, docker_image: str, spec_path: Optional[str] = None, use_ai: bool = False, run_security: bool = False, language: str = "python") -> None:
        """Run comprehensive health checks on system and Docker image"""
        print("🔍 Running Claude Agent Health Check...")
        
        # Security: Sanitize inputs
        try:
            docker_image = self._sanitize_docker_image(docker_image)
        except ValueError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
        
        print(f"Docker Image: {docker_image}")
        print(f"Language: {language}")
        if spec_path:
            print(f"Spec File: {spec_path}")
        print("-" * 60)
        
        checks_passed = 0
        total_checks = 0
        issues = []
        
        # Check 1: Spec clarity (if provided)
        if spec_path:
            total_checks += 1
            if use_ai:
                print("🤖 Running AI-powered spec analysis...")
                ai_result, ai_issues = self._ai_analyze_spec(spec_path, docker_image)
                if ai_result:
                    print("  ✅ AI analysis: Spec is well-structured and actionable")
                    checks_passed += 1
                else:
                    print("  ❌ AI analysis: Spec needs improvement")
                    issues.extend(ai_issues)
            else:
                print("📄 Checking spec file clarity...")
                spec_result, spec_issues = self._check_spec_clarity(spec_path)
                if spec_result:
                    print("  ✅ Spec file is clear and actionable")
                    checks_passed += 1
                else:
                    print("  ❌ Spec file has clarity issues")
                    issues.extend(spec_issues)
        
        # Check 2: Docker image git repository compatibility
        total_checks += 1
        print("🐳 Checking Docker image git compatibility...")
        docker_result, docker_issues = self._check_docker_git_compatibility(docker_image)
        if docker_result:
            print("  ✅ Docker image has working git setup")
            checks_passed += 1
        else:
            print("  ❌ Docker image has git issues")
            issues.extend(docker_issues)
        
        # Check 3: Language-specific toolchain validation
        total_checks += 1
        print(f"🔧 Checking {language} toolchain compatibility...")
        toolchain_result, toolchain_issues = self._check_language_toolchain(docker_image, language)
        if toolchain_result:
            print(f"  ✅ {language.title()} toolchain is available and functional")
            checks_passed += 1
        else:
            print(f"  ❌ {language.title()} toolchain has issues")
            issues.extend(toolchain_issues)
        
        # Check 4: Docker security scan (optional)
        if run_security:
            total_checks += 1
            print("🛡️  Checking Docker image security...")
            security_result, security_issues = self._check_docker_security(docker_image)
            if security_result:
                print("  ✅ Docker image security scan passed")
                checks_passed += 1
            else:
                print("  ⚠️  Docker image has security concerns")
                issues.extend(security_issues)
        else:
            print("🛡️  Docker security scan skipped (use --security to enable)")
        
        # Check 5: System prerequisites
        total_checks += 1
        print("⚙️ Checking system prerequisites...")
        system_result, system_issues = self._check_system_prerequisites()
        if system_result:
            print("  ✅ All system prerequisites available")
            checks_passed += 1
        else:
            print("  ❌ System prerequisites missing")
            issues.extend(system_issues)
        
        # Summary
        print("-" * 60)
        if checks_passed == total_checks:
            print(f"✅ Health Check PASSED ({checks_passed}/{total_checks})")
            print("🚀 System is ready to run Claude Agent jobs!")
        else:
            print(f"❌ Health Check FAILED ({checks_passed}/{total_checks})")
            print(f"\n🔧 Issues found ({len(issues)} total):")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            print(f"\nPlease fix these {len(issues)} issues before running jobs.")
            sys.exit(1)
    
    def _check_spec_clarity(self, spec_path: str) -> tuple[bool, list[str]]:
        """Check if spec file is clear and actionable"""
        issues = []
        
        try:
            with open(spec_path, 'r') as f:
                content = f.read()
        except Exception as e:
            return False, [f"Cannot read spec file: {e}"]
        
        if not content.strip():
            return False, ["Spec file is empty"]
        
        # Check for clarity indicators
        content_lower = content.lower()
        lines = content.split('\n')
        
        # Check for actionable content
        action_words = ['implement', 'fix', 'add', 'remove', 'update', 'create', 'modify', 'change']
        has_action = any(word in content_lower for word in action_words)
        if not has_action:
            issues.append("Spec lacks clear action words (implement, fix, add, etc.)")
        
        # Check for structure
        if len(lines) < 3:
            issues.append("Spec is too short - add more detail")
        
        # Check for vague language
        vague_phrases = ['make it better', 'fix issues', 'improve performance', 'clean up']
        vague_found = [phrase for phrase in vague_phrases if phrase in content_lower]
        if vague_found:
            issues.append(f"Spec contains vague language: {', '.join(vague_found)}")
        
        # Check for requirements/acceptance criteria
        has_requirements = any(keyword in content_lower for keyword in 
                              ['requirement', 'criteria', 'should', 'must', 'expected'])
        if not has_requirements:
            issues.append("Spec should include clear requirements or acceptance criteria")
        
        # Check for excessive length (likely to cause oversized PRs)
        if len(lines) > 100:
            issues.append("Spec is very long - may result in oversized PR")
        
        return len(issues) == 0, issues
    
    def _ai_analyze_spec(self, spec_path: str, docker_image: str) -> Tuple[bool, List[str]]:
        """Use AI agent to analyze spec quality and provide detailed feedback"""
        issues = []
        
        try:
            # Read spec content
            content = self.read_spec_file(spec_path)
            
            # Create analysis prompt
            analysis_prompt = f"""Analyze this technical specification for a Claude Code agent that will work in Docker image '{docker_image}'. 

SPECIFICATION TO ANALYZE:
{content}

Please evaluate these aspects:
1. **Clarity**: Are the goals and requirements clearly defined?
2. **Completeness**: Are sufficient technical details provided?
3. **Actionability**: Can an AI agent immediately start implementing this?
4. **Scope**: Is this appropriately sized for a single implementation?
5. **Context**: Are technical constraints and environment details clear?

Provide:
- **OVERALL SCORE**: Rate 1-10 (7+ means ready for implementation)
- **KEY ISSUES**: List 3-5 most critical problems if score < 7
- **QUICK FIXES**: Suggest specific improvements needed

Focus on practical implementation concerns for an autonomous AI agent."""

            # Run Claude Code analysis directly
            print("  🤖 Running AI spec analysis...")
            result = subprocess.run([
                "claude", "--print", analysis_prompt
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                issues.append(f"AI analysis failed: {result.stderr.strip()}")
                return False, issues
            
            # Parse the AI response
            ai_response = result.stdout.strip()
            
            # Extract score
            score = 5  # Default fallback score
            if "OVERALL SCORE" in ai_response or "SCORE" in ai_response:
                try:
                    # Look for score patterns like "8/10", "Score: 7", etc.
                    import re
                    score_match = re.search(r'(?:SCORE|Score)[:\s]*(\d+)(?:/10)?', ai_response, re.IGNORECASE)
                    if score_match:
                        score = int(score_match.group(1))
                except (ValueError, AttributeError):
                    pass
            
            print(f"  📊 AI Analysis Score: {score}/10")
            
            # If score is too low, extract issues
            if score < 7:
                # Look for issues section
                if "KEY ISSUES" in ai_response or "ISSUES" in ai_response:
                    lines = ai_response.split('\n')
                    in_issues = False
                    for line in lines:
                        line = line.strip()
                        if any(keyword in line.upper() for keyword in ["KEY ISSUES", "ISSUES", "PROBLEMS"]):
                            in_issues = True
                            continue
                        elif any(keyword in line.upper() for keyword in ["QUICK FIXES", "SUGGESTIONS", "FIXES"]):
                            break
                        elif in_issues and line and not line.startswith('#'):
                            # Clean up the line and add as issue
                            clean_line = line.lstrip('- •*').strip()
                            if clean_line:
                                issues.append(f"AI: {clean_line}")
                
                # Fallback if no specific issues found
                if not issues:
                    issues.append(f"AI analysis indicates spec needs improvement (score: {score}/10)")
            
            if issues:
                print(f"  📝 Found {len(issues)} areas for improvement")
                
        except subprocess.TimeoutExpired:
            issues.append("AI analysis timed out (>60 seconds)")
        except Exception as e:
            issues.append(f"AI analysis error: {e}")
        
        return len(issues) == 0, issues
    
    def _check_docker_git_compatibility(self, docker_image: str) -> tuple[bool, list[str]]:
        """Check if Docker image has working git setup"""
        issues = []
        
        try:
            # Check if Docker is available
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                return False, ["Docker is not installed or not accessible"]
            
            # Check if image exists or can be pulled
            print(f"  🔍 Checking if image '{docker_image}' is available...")
            result = subprocess.run(['docker', 'image', 'inspect', docker_image], 
                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"  📥 Pulling image '{docker_image}'...")
                pull_result = subprocess.run(['docker', 'pull', docker_image], 
                                           capture_output=True, text=True)
                if pull_result.returncode != 0:
                    issues.append(f"Cannot pull Docker image '{docker_image}': {pull_result.stderr.strip()}")
                    return False, issues
            
            # Test git functionality in the image
            print("  🧪 Testing git functionality in container...")
            git_test_cmd = [
                'docker', 'run', '--rm', 
                docker_image,
                'sh', '-c', 'git --version && echo "Git check: OK"'
            ]
            
            result = subprocess.run(git_test_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                issues.append("Git is not installed or not working in the Docker image")
            
            # Test basic shell functionality
            print("  🧪 Testing shell functionality...")
            shell_test_cmd = [
                'docker', 'run', '--rm',
                docker_image, 
                'sh', '-c', 'echo "Shell check: OK" && ls /'
            ]
            
            result = subprocess.run(shell_test_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                issues.append("Basic shell functionality not working in Docker image")
            
            # Test if we can install curl (needed for Claude Code installation)
            print("  🧪 Testing package installation capability...")
            package_test_cmd = [
                'docker', 'run', '--rm',
                docker_image,
                'sh', '-c', '''
                if command -v apt-get >/dev/null 2>&1; then
                    apt-get update >/dev/null 2>&1 && echo "Package manager: apt-get OK"
                elif command -v apk >/dev/null 2>&1; then
                    echo "Package manager: apk OK"
                elif command -v yum >/dev/null 2>&1; then
                    echo "Package manager: yum OK"
                else
                    exit 1
                fi
                '''
            ]
            
            result = subprocess.run(package_test_cmd, capture_output=True, text=True, timeout=45)
            if result.returncode != 0:
                issues.append("No compatible package manager found (need apt-get, apk, or yum)")
            
        except subprocess.TimeoutExpired:
            issues.append("Docker operations timed out - image may be too large or slow")
        except Exception as e:
            issues.append(f"Error testing Docker image: {e}")
        
        return len(issues) == 0, issues
    
    def _check_docker_security(self, docker_image: str) -> tuple[bool, list[str]]:
        """Check Docker image for security vulnerabilities using Trivy"""
        issues = []
        
        # Check if Trivy is available
        try:
            result = subprocess.run(['trivy', 'version'], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                issues.append("Trivy not installed - install with: curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin")
                return False, issues
        except FileNotFoundError:
            issues.append("Trivy not found - install from: https://aquasecurity.github.io/trivy/latest/getting-started/installation/")
            return False, issues
        except subprocess.TimeoutExpired:
            issues.append("Trivy command timed out")
            return False, issues
        except Exception as e:
            issues.append(f"Error checking Trivy: {e}")
            return False, issues
        
        # Run Trivy security scan
        try:
            print(f"    🔍 Scanning {docker_image} for vulnerabilities...")
            result = subprocess.run([
                'trivy', 'image', 
                '--exit-code', '1',  # Exit with code 1 if vulnerabilities found
                '--severity', 'HIGH,CRITICAL',  # Only check high/critical
                '--quiet',  # Reduce output
                '--format', 'json',
                docker_image
            ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
            
            if result.returncode == 0:
                print(f"    ✅ No high/critical vulnerabilities found")
                return True, []
            else:
                # Parse JSON output to count vulnerabilities
                try:
                    import json
                    scan_data = json.loads(result.stdout)
                    vuln_count = 0
                    for result_item in scan_data.get('Results', []):
                        vuln_count += len(result_item.get('Vulnerabilities', []))
                    
                    if vuln_count > 0:
                        issues.append(f"Found {vuln_count} high/critical vulnerabilities in {docker_image}")
                        issues.append("Run 'trivy image --severity HIGH,CRITICAL <image>' for details")
                        return False, issues
                except json.JSONDecodeError:
                    issues.append(f"Vulnerabilities detected in {docker_image} (run 'trivy image {docker_image}' for details)")
                    return False, issues
                    
        except subprocess.TimeoutExpired:
            issues.append(f"Security scan of {docker_image} timed out (large images may take time)")
            return False, issues
        except Exception as e:
            issues.append(f"Error running security scan: {e}")
            return False, issues
        
        return True, []
    
    def _check_language_toolchain(self, docker_image: str, language: str) -> tuple[bool, list[str]]:
        """Check if language-specific toolchain is available in Docker image"""
        issues = []
        
        try:
            if language == "python":
                # Check Python interpreter and pip
                result = subprocess.run([
                    "docker", "run", "--rm", docker_image, "python", "--version"
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    issues.append("Python interpreter not found")
                
                # Check pip
                result = subprocess.run([
                    "docker", "run", "--rm", docker_image, "pip", "--version"
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    issues.append("pip not found")
                
            elif language == "rust":
                # Check Rust compiler
                result = subprocess.run([
                    "docker", "run", "--rm", docker_image, "rustc", "--version"
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    issues.append("Rust compiler (rustc) not found")
                
                # Check Cargo
                result = subprocess.run([
                    "docker", "run", "--rm", docker_image, "cargo", "--version"
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    issues.append("Cargo package manager not found")
            
            else:
                issues.append(f"Unknown language: {language}")
            
        except subprocess.TimeoutExpired:
            issues.append("Toolchain check timed out")
        except Exception as e:
            issues.append(f"Error checking toolchain: {e}")
        
        return len(issues) == 0, issues
    
    def _check_system_prerequisites(self) -> tuple[bool, list[str]]:
        """Check if all required system tools are available"""
        issues = []
        
        # Check required tools
        required_tools = [
            ('docker', 'Docker'),
            ('gh', 'GitHub CLI'),
            ('git', 'Git')
        ]
        
        for tool, name in required_tools:
            try:
                result = subprocess.run([tool, '--version'], capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    issues.append(f"{name} is not installed or not working")
            except FileNotFoundError:
                issues.append(f"{name} ({tool}) is not installed")
            except subprocess.TimeoutExpired:
                issues.append(f"{name} ({tool}) command timed out")
            except Exception as e:
                issues.append(f"Error checking {name}: {e}")
        
        # Check GitHub CLI authentication
        try:
            result = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                issues.append("GitHub CLI is not authenticated (run 'gh auth login')")
        except Exception as e:
            issues.append(f"Cannot check GitHub CLI auth status: {e}")
        
        # Check for ANTHROPIC_API_KEY
        if 'ANTHROPIC_API_KEY' not in os.environ:
            issues.append("ANTHROPIC_API_KEY environment variable is not set")
        elif not os.environ['ANTHROPIC_API_KEY'].strip():
            issues.append("ANTHROPIC_API_KEY environment variable is empty")
        
        # Check git configuration
        try:
            name_result = subprocess.run(['git', 'config', 'user.name'], 
                                       capture_output=True, text=True, timeout=5)
            email_result = subprocess.run(['git', 'config', 'user.email'], 
                                        capture_output=True, text=True, timeout=5)
            
            if name_result.returncode != 0 or not name_result.stdout.strip():
                issues.append("Git user.name is not configured (run 'git config --global user.name \"Your Name\"')")
            
            if email_result.returncode != 0 or not email_result.stdout.strip():
                issues.append("Git user.email is not configured (run 'git config --global user.email \"you@example.com\"')")
                
        except Exception as e:
            issues.append(f"Cannot check git configuration: {e}")
        
        return len(issues) == 0, issues

    def run_daemon_mode(self, args: argparse.Namespace) -> None:
        """Run agent in background daemon mode"""
        # Read inputs
        spec_content = ""
        issue_title = ""
        issue_body = ""
        issue_number = None

        if args.spec:
            spec_content = self.read_spec_file(args.spec)

        if args.issue:
            issue_title, issue_body = self.fetch_issue_content(args.issue)
            issue_number = args.issue.split("/")[-1]

        if args.pr:
            # Extract task specification from PR comments
            task_spec = self.fetch_pr_tasks(args.pr)
            # Get PR details to determine branch
            pr_data = self.get_pr_details(args.pr)
            if pr_data and pr_data.get('headRefName'):
                args.branch = pr_data['headRefName']  # Use existing PR branch
                print(f"📋 Using existing PR branch: {args.branch}")
            # Store PR number for container environment
            self._current_pr_number = args.pr
        else:
            # Merge specifications for issue/spec mode
            task_spec = self.merge_specifications(spec_content, issue_title, issue_body)

        # Handle cost estimation if requested
        if args.cost_estimate:
            task_type = "PR continuation" if args.pr else "new task"
            estimate = self.estimate_task_cost(task_spec, args.language)
            self.print_cost_estimate(estimate, f"{task_type} (background job)")
            
            # Ask user if they want to proceed
            if estimate and estimate.get("estimated_total_cost", 0) > 0.10:  # Alert for costs > $0.10
                response = input("💰 Estimated cost is significant. Start background job? [y/N]: ").lower()
                if response != 'y':
                    print("⏹️  Background job cancelled by user")
                    return
            elif estimate:
                response = input("💰 Start background job? [Y/n]: ").lower()
                if response == 'n':
                    print("⏹️  Background job cancelled by user")
                    return
            
            print("🚀 Starting background job...\n")

        # Create background job
        job_id = self.job_manager.create_job(
            task_spec=task_spec,
            base_image=args.base_image,
            branch_name=args.branch,
            base_branch=args.base_branch,
            github_issue=args.issue,
        )

        print(f"🚀 Started background job: {job_id}")
        print(f"📋 Branch: {args.branch}")
        print(f"🐳 Base image: {args.base_image}")

        # Start container in background
        success = self.execute_claude_code_daemon(
            task_spec,
            args.base_image,
            args.branch,
            args.base_branch,
            job_id,
            issue_number,
            args.language,
            args.reviewer,
            args.env,
            args.volume,
        )

        if success:
            print(f"✅ Job {job_id} started successfully")
            print(
                f"💡 Monitor with: python3 claude_agent.py status --job-id {job_id}"
            )
        else:
            print(f"❌ Failed to start job {job_id}")
            self.job_manager.update_job_status(
                job_id, "failed", error_message="Failed to start container"
            )

    def execute_claude_code_daemon(
        self,
        task_spec: str,
        base_image: str,
        branch_name: str,
        base_branch: str,
        job_id: str,
        issue_number: Optional[str] = None,
        language: str = "python",
        reviewer: Optional[str] = None,
        custom_env: Optional[List[str]] = None,
        custom_volumes: Optional[List[str]] = None,
    ) -> bool:
        """Execute Claude Code in background daemon mode"""
        try:
            # Build agent image
            agent_image = self.build_agent_image(base_image)
            if not agent_image:
                return False

            # Start container in background
            container_id = self.start_background_container(
                agent_image, task_spec, branch_name, base_branch, issue_number, reviewer, custom_env, custom_volumes, language, job_id
            )

            if container_id:
                # Update job with container ID and start monitoring
                self.job_manager.update_job_status(
                    job_id, "running", container_id=container_id
                )
                self.job_manager.monitor_job(job_id, container_id)
                return True
            else:
                return False

        except Exception as e:
            print(f"❌ Error starting daemon job: {e}")
            return False

    def start_background_container(
        self,
        image: str,
        task_spec: str,
        branch_name: str,
        base_branch: str,
        issue_number: Optional[str] = None,
        reviewer: Optional[str] = None,
        custom_env: Optional[List[str]] = None,
        custom_volumes: Optional[List[str]] = None,
        language: str = "python",
        job_id: Optional[str] = None,
    ) -> Optional[str]:
        """Start Docker container in background and return container ID"""
        try:
            # Write task spec to temporary file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(task_spec)
                spec_file = f.name

            # Get paths to utilities
            github_utils_path = Path(__file__).parent / "github_utils.py"
            cost_monitor_path = Path(__file__).parent / "claude_cost_monitor.py"
            
            # Create job-specific directory for cost data exchange
            if job_id:
                cost_data_dir = Path.cwd() / ".claude_cost_data" / job_id
            else:
                cost_data_dir = Path.cwd() / ".claude_cost_data" / f"temp_{hash(spec_file)}"
            cost_data_dir.mkdir(parents=True, exist_ok=True)

            # Prepare Docker command for background execution
            docker_cmd = [
                "docker",
                "run",
                "--detach",  # Run in background
                "-v",
                spec_file + ":/tmp/task_spec.md",
                "-v",
                f"{github_utils_path}:/usr/local/bin/github_utils.py",
                "-v",
                f"{cost_monitor_path}:/usr/local/bin/claude_cost_monitor.py",
                "-v", 
                f"{cost_data_dir}:/tmp/cost_data",
            ]

            # Security: Mount credentials with path validation
            try:
                gitconfig_path = Path.home() / ".gitconfig"
                if gitconfig_path.exists():
                    validated_path = self._validate_mount_path(gitconfig_path, "Git config")
                    docker_cmd.extend(["-v", f"{validated_path}:/root/.gitconfig"])
                
                ssh_path = Path.home() / ".ssh"
                if ssh_path.exists():
                    validated_path = self._validate_mount_path(ssh_path, "SSH directory")
                    docker_cmd.extend(["-v", f"{validated_path}:/root/.ssh"])
                
                gh_config_path = Path.home() / ".config/gh"
                if gh_config_path.exists():
                    validated_path = self._validate_mount_path(gh_config_path, "GitHub CLI config")
                    docker_cmd.extend(["-v", f"{validated_path}:/root/.config/gh"])
                    
            except ValueError as e:
                print(f"⚠️  Warning: Skipping credential mount: {e}")
                # Continue without these credentials rather than failing

            # Process custom volumes with security validation
            if custom_volumes:
                for volume_spec in custom_volumes:
                    try:
                        # Parse volume specification: "host_path:container_path" or "host_path:container_path:options"
                        parts = volume_spec.split(":")
                        if len(parts) < 2:
                            print(f"⚠️  Warning: Invalid volume specification: {volume_spec}")
                            continue
                        
                        host_path = parts[0]
                        container_path = parts[1]
                        options = parts[2] if len(parts) > 2 else ""
                        
                        # Validate host path exists and is accessible
                        host_path_obj = Path(host_path)
                        if not host_path_obj.exists():
                            print(f"⚠️  Warning: Host path does not exist: {host_path}")
                            continue
                        
                        # Security validation for host paths
                        validated_host_path = self._validate_mount_path(host_path_obj, f"Custom volume {host_path}")
                        
                        # Build volume mount string
                        volume_mount = f"{validated_host_path}:{container_path}"
                        if options:
                            volume_mount += f":{options}"
                        
                        docker_cmd.extend(["-v", volume_mount])
                        print(f"  📁 Added volume mount: {host_path} -> {container_path}")
                        
                    except (ValueError, IndexError) as e:
                        print(f"⚠️  Warning: Skipping invalid volume mount {volume_spec}: {e}")
                        continue

            # Add environment variables (secure credential handling)
            env_vars = []
            api_key_file = None
            if "ANTHROPIC_API_KEY" in os.environ:
                # Write API key to temporary file for secure mounting
                api_key_fd, api_key_path = tempfile.mkstemp(suffix=".key", prefix="anthropic_")
                try:
                    with os.fdopen(api_key_fd, 'w') as f:
                        f.write(os.environ['ANTHROPIC_API_KEY'])
                    api_key_file = api_key_path
                    # Mount API key as file instead of environment variable
                    docker_cmd.extend(["-v", f"{api_key_path}:/run/secrets/anthropic_api_key:ro"])
                    # Set environment variable to point to the mounted file
                    env_vars.extend(["-e", "ANTHROPIC_API_KEY_FILE=/run/secrets/anthropic_api_key"])
                except Exception as e:
                    print(f"⚠️  Warning: Could not create secure API key file: {e}")
                    # Fallback to environment variable (less secure)
                    env_vars.extend(["-e", f"ANTHROPIC_API_KEY={os.environ['ANTHROPIC_API_KEY']}"]) 
                    if api_key_file:
                        try:
                            os.unlink(api_key_file)
                        except OSError:
                            pass
                        api_key_file = None
            if issue_number:
                env_vars.extend(["-e", f"GITHUB_ISSUE_NUMBER={issue_number}"])
            if hasattr(self, '_current_pr_number') and self._current_pr_number:
                env_vars.extend(["-e", f"PR_NUMBER={self._current_pr_number}"])
            env_vars.extend(["-e", f"BASE_BRANCH={base_branch}"])
            env_vars.extend(["-e", f"BRANCH_NAME={branch_name}"])
            env_vars.extend(["-e", "TASK_SPEC_FILE=/tmp/task_spec.md"])
            env_vars.extend(["-e", f"LANGUAGE={language}"])
            if reviewer:
                env_vars.extend(["-e", f"DEFAULT_REVIEWER={reviewer}"])
            
            # Process custom environment variables
            if custom_env:
                for env_spec in custom_env:
                    try:
                        # Parse environment variable: "KEY=value"
                        if "=" not in env_spec:
                            print(f"⚠️  Warning: Invalid environment variable specification: {env_spec}")
                            continue
                        
                        key, value = env_spec.split("=", 1)
                        
                        # Basic validation of environment variable key
                        if not key or not key.replace("_", "").replace("-", "").isalnum():
                            print(f"⚠️  Warning: Invalid environment variable key: {key}")
                            continue
                        
                        env_vars.extend(["-e", f"{key}={value}"])
                        print(f"  🔧 Added environment variable: {key}")
                        
                    except ValueError as e:
                        print(f"⚠️  Warning: Skipping invalid environment variable {env_spec}: {e}")
                        continue

            docker_cmd.extend(env_vars)
            docker_cmd.append(image)

            # Execute container in background
            result = subprocess.run(docker_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                container_id = result.stdout.strip()
                print(f"🐳 Started container: {container_id[:12]}...")
                return container_id
            else:
                print(f"❌ Failed to start container: {result.stderr}")
                # Cleanup temp files
                Path(spec_file).unlink(missing_ok=True)
                if api_key_file:
                    try:
                        os.unlink(api_key_file)
                    except OSError:
                        pass
                return None

        except Exception as e:
            print(f"❌ Error starting background container: {e}")
            # Cleanup temp files on exception
            if 'spec_file' in locals():
                Path(spec_file).unlink(missing_ok=True)
            if 'api_key_file' in locals() and api_key_file:
                try:
                    os.unlink(api_key_file)
                except OSError:
                    pass
            return None


if __name__ == "__main__":
    # Parse arguments to get configuration values
    temp_agent = ClaudeAgent()
    args = temp_agent.parse_args()
    
    # Create agent with parsed configuration
    agent = ClaudeAgent(
        reviewer_username=getattr(args, 'reviewer', 'vikranth22446'),
        max_lines=getattr(args, 'max_lines', 600),
        warn_lines=getattr(args, 'warn_lines', 300)
    )
    agent.run()
