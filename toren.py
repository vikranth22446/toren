#!/usr/bin/env python3
"""
Claude Agent Worker - Autonomous GitHub Issue/Spec Processor
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from ai_cli_interface import AICliInterface
from cli_parser import CLIParser
from container_manager import ContainerManager
from github_utils import GitHubUtils
from input_validator import InputValidator
from job_manager import JobManager
from ui_utilities import UIUtilities


class ClaudeAgent:
    def __init__(
        self,
        reviewer_username: str = "vikranth22446",
        max_lines: int = 400,
        warn_lines: int = 300,
    ):
        self.reviewer_username = reviewer_username
        self.max_lines = max_lines
        self.warn_lines = warn_lines
        self.job_manager = JobManager()
        self.validator = InputValidator()
        self.ai_cli = AICliInterface()
        self.container_manager = ContainerManager(self.validator)
        self.github_utils = GitHubUtils(reviewer_username)
        self.ui = UIUtilities(
            self.job_manager, self.validator, self.ai_cli, self.container_manager
        )

        self.config = self._load_config()
        self.cli_parser = CLIParser(reviewer_username, self.config)

    def parse_args(self) -> argparse.Namespace:
        """Parse command line arguments"""
        return self.cli_parser.parse_args()

    def run(self) -> None:
        """Main execution flow"""
        args = self.parse_args()

        if args.command is None:
            # Show help text when no command is provided
            self.cli_parser._parser.print_help()
            sys.exit(0)
        elif args.command == "run":
            self.run_daemon_mode(args)
        elif args.command == "status":
            self.ui.show_status(args.job_id, args.filter)
        elif args.command == "summary":
            self.ui.show_summary(args.job_id)
        elif args.command == "logs":
            self.ui.show_logs(args.job_id, args.follow)
        elif args.command == "cleanup":
            self.ui.cleanup_jobs(args.job_id, args.all, args.force)
        elif args.command == "kill":
            self.ui.kill_job(args.job_id)
        elif args.command == "health":
            self.ui.run_health_check(
                args.docker_image, args.spec, args.ai, args.security, args.language
            )
        elif args.command == "update-base-image":
            if not args.image:
                print("❌ Error: --image is required for update-base-image command")
                sys.exit(1)
            self.ui.update_base_image(args.image)
        else:
            print("❌ Unknown command")
            sys.exit(1)

    def _load_config(self) -> dict:
        """Load configuration from config.json in current working directory"""
        config_path = Path.cwd() / "config.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                print(f"⚠️ Invalid JSON in config file {config_path}: {e}")
            except PermissionError:
                print(f"⚠️ Permission denied reading config file {config_path}")
            except OSError as e:
                print(f"⚠️ Error reading config file {config_path}: {e}")
        return {}

    def _get_anthropic_api_key(self) -> Optional[str]:
        """Get Anthropic API key from environment or ~/.claude.json fallback"""
        if (
            "ANTHROPIC_API_KEY" in os.environ
            and os.environ["ANTHROPIC_API_KEY"].strip()
        ):
            return os.environ["ANTHROPIC_API_KEY"]
        return None

    def read_spec_file(self, spec_path: str) -> str:
        """Read markdown specification file"""
        try:
            with open(spec_path, "r") as f:
                return f.read()
        except Exception as e:
            print(f"❌ Error reading spec file: {e}")
            return ""

    def handle_short_description(self, short_desc: str) -> str:
        """Handle short description with quality checking"""
        truncated = short_desc[:100] + "..." if len(short_desc) > 100 else short_desc
        print(f"📝 Processing short description: {truncated}")

        # Check quality of the short description
        # quality = self.ai_cli.check_short_description_quality(short_desc)
        # self.ai_cli.print_quality_assessment(quality)

        # If description is unclear, prompt user
        # if not quality.get("is_clear", False):
        #     print("⚠️  The description may be unclear or lack sufficient detail.")
        #     response = input("Continue anyway? [y/N]: ").lower()
        #     if response != "y":
        #         print("⏹️  Task cancelled by user")
        #         sys.exit(0)

        # Return the short description as the spec content
        return f"## Task Description\n{short_desc}"

    def merge_specifications(
        self, spec_content: str, issue_title: str, issue_body: str
    ) -> str:
        """Combine spec file and issue into unified task description"""
        merged = []

        if issue_title and issue_body:
            merged.append(f"## GitHub Issue: {issue_title}\n{issue_body}")

        if spec_content:
            merged.append(f"## Specification\n{spec_content}")

        merged.append(
            f"""
## PR Guidelines
- Keep changes under {self.max_lines} lines (warn at {self.warn_lines})
- Follow existing codebase style and patterns
- Avoid excessive comments and tests
- Prefer simple, straightforward solutions
- Don't over-engineer
- Follow the specification precisely unless safety concerns arise
"""
        )

        return "\n\n".join(merged)

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

    def run_daemon_mode(self, args: argparse.Namespace) -> None:
        """Run agent in background daemon mode"""
        # Create CLI interface for the specified type
        self.ai_cli = AICliInterface(args.cli_type)

        spec_content = ""
        issue_title = ""
        issue_body = ""
        issue_number = None

        # Validate spec/short arguments
        if args.spec and args.short:
            print("❌ Error: Cannot specify both --spec and --short. Choose one.")
            sys.exit(1)

        if args.spec:
            spec_content = self.read_spec_file(args.spec)
        elif args.short:
            spec_content = self.handle_short_description(args.short)

        if args.issue:
            issue_number = args.issue.split("/")[-1]
            issue_data = self.github_utils.get_issue(issue_number)
            issue_title = issue_data.get("title", "") if issue_data else ""
            issue_body = issue_data.get("body", "") if issue_data else ""

        if args.pr:
            task_spec = self.github_utils.extract_claude_tasks_from_pr(args.pr)
            pr_data = self.github_utils.get_pr(args.pr)
            if pr_data and pr_data.get("headRefName"):
                args.branch = pr_data["headRefName"]
                print(f"📋 Using existing PR branch: {args.branch}")
            else:
                print(f"❌ Error: Could not determine branch for PR #{args.pr}")
                return
            self._current_pr_number = args.pr
        else:
            task_spec = self.merge_specifications(spec_content, issue_title, issue_body)

        if args.cost_estimate:
            task_type = "PR continuation" if args.pr else "new task"
            estimate = self.ai_cli.estimate_task_cost(task_spec, args.language)
            if estimate:
                self.ai_cli.print_cost_estimate(estimate, f"{task_type} (background job)")

            if estimate and estimate.get("estimated_total_cost", 0) > 0.10:
                response = input(
                    "💰 Estimated cost is significant. Start background job? [y/N]: "
                ).lower()
                if response != "y":
                    print("⏹️  Background job cancelled by user")
                    return
            elif estimate:
                response = input("💰 Start background job? [Y/n]: ").lower()
                if response == "n":
                    print("⏹️  Background job cancelled by user")
                    return

            print("🚀 Starting background job...\n")

        job_id = self.job_manager.create_job(
            task_spec=task_spec,
            base_image=args.base_image,
            branch_name=args.branch,
            base_branch=args.base_branch,
            github_issue=args.issue,
            cli_type=args.cli_type,
        )

        print(f"🚀 Started background job: {job_id}")
        print(f"📋 Branch: {args.branch}")
        print(f"🐳 Base image: {args.base_image}")

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
            args.cli_type,
        )

        if success:
            print(f"✅ Job {job_id} started successfully")
            print(f"💡 Monitor with: toren status --job-id {job_id}")
            print(f"📋 View logs: toren logs {job_id}")
            print(f"📊 Get summary: toren summary {job_id}")
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
        cli_type: str = "claude",
    ) -> bool:
        """Execute Claude Code in background daemon mode"""
        try:
            agent_image = self.container_manager.build_agent_image(base_image, cli_type)
            if not agent_image:
                return False

            github_token = os.environ.get("GITHUB_TOKEN")
            anthropic_api_key = self._get_anthropic_api_key()

            container_process = self.container_manager.execute_in_container(
                agent_image,
                branch_name,
                task_spec,
                github_token,
                anthropic_api_key,
                job_id,
                custom_env,
                custom_volumes,
                cli_type,
                issue_number,
            )

            container_id = f"{cli_type}-agent-{job_id}" if container_process else None

            if container_id:
                self.job_manager.update_job_status(
                    job_id,
                    "running",
                    container_id=container_id,
                    agent_image=agent_image,
                )
                self.job_manager.monitor_job(job_id, container_id)
                return True
            else:
                return False

        except Exception as e:
            print(f"❌ Error starting daemon job: {e}")
            return False


def main():
    """Main entry point for the toren CLI"""
    temp_agent = ClaudeAgent()
    args = temp_agent.parse_args()

    agent = ClaudeAgent(
        reviewer_username=getattr(args, "reviewer", "vikranth22446"),
        max_lines=getattr(args, "max_lines", 600),
        warn_lines=getattr(args, "warn_lines", 300),
    )
    agent.run()


if __name__ == "__main__":
    main()
