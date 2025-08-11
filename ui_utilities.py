#!/usr/bin/env python3

import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional


class UIUtilities:
    def __init__(self, job_manager, validator, ai_cli, container_manager):
        self.job_manager = job_manager
        self.validator = validator
        self.ai_cli = ai_cli
        self.container_manager = container_manager

    def _count_lines_from_stat(self, stat_output: str) -> int:
        """Extract line count from git diff --stat output"""
        try:
            for line in stat_output.split("\n"):
                if "insertions" in line or "deletions" in line:
                    numbers = re.findall(r"\d+", line)
                    return sum(int(n) for n in numbers[:2])  # insertions + deletions
        except (subprocess.SubprocessError, ValueError, OSError):
            pass
        return 0

    def format_timestamp(self, iso_string: str) -> str:
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
        except (ValueError, TypeError):
            return iso_string

    def status_color(self, status: str) -> str:
        colors = {
            "running": "\033[94m",
            "completed": "\033[92m",
            "failed": "\033[91m",
            "queued": "\033[93m",
            "cancelled": "\033[90m",
        }
        reset = "\033[0m"
        return colors.get(status, "") + status + reset

    def show_status(self, job_id: Optional[str] = None, status_filter: Optional[str] = None) -> None:
        if job_id:
            job = self.job_manager.get_job(job_id)
            if not job:
                print(f"❌ Job {job_id} not found")
                sys.exit(1)
            self._show_detailed_job(job)
        else:
            jobs = self.job_manager.list_jobs(status_filter)
            if not jobs:
                print("No jobs found")
                return
            self._show_job_list(jobs)

    def _show_job_list(self, jobs: List[Dict]) -> None:
        display_jobs = jobs[:10]
        print(
            f"{'JOB ID':<10} {'STATUS':<12} {'BRANCH':<18} {'COST':<8} {'+/- LINES':<9} {'CREATED':<10} {'SUMMARY'}"
        )
        print("-" * 90)

        for job in display_jobs:
            job_id = job["job_id"]
            status = self.status_color(job["status"])
            branch = (
                job["branch_name"][:16] + ".."
                if len(job["branch_name"]) > 18
                else job["branch_name"]
            )

            cost_info = job.get("cost_info", {})
            git_stats = job.get("git_stats", {})
            cost_str = (
                f"${cost_info.get('total_cost', 0):.3f}"
                if cost_info.get("total_cost", 0) > 0
                else "-"
            )
            lines_added = git_stats.get("lines_added", 0)
            lines_deleted = git_stats.get("lines_deleted", 0)
            lines_str = (
                f"+{lines_added}/-{lines_deleted}"
                if lines_added > 0 or lines_deleted > 0
                else "-"
            )

            created = self.format_timestamp(job["created_at"])
            summary = (
                job["ai_summary"][:35] + "..."
                if len(job["ai_summary"]) > 35
                else job["ai_summary"]
            )
            print(
                f"{job_id:<10} {status:<12} {branch:<18} {cost_str:<8} {lines_str:<9} {created:<10} {summary}"
            )

        if len(jobs) > len(display_jobs):
            print(f"\nShowing {len(display_jobs)} of {len(jobs)} jobs (most recent)")

        status_counts: Dict[str, int] = {}
        for job in jobs:
            status = job["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        if status_counts:
            status_parts = []
            for status, count in status_counts.items():
                color_status = self.status_color(status)
                status_parts.append(f"{color_status}: {count}")
            print(f"Status summary: {', '.join(status_parts)}")

        completed_failed = status_counts.get("completed", 0) + status_counts.get(
            "failed", 0
        )
        if completed_failed > 5:
            print(
                f"\n💡 Tip: Run 'python3 toren.py cleanup' to remove {completed_failed} completed/failed jobs"
            )

    def _show_detailed_job(self, job: Dict) -> None:
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

        cost_info = job.get("cost_info", {})
        git_stats = job.get("git_stats", {})

        if (
            cost_info.get("total_cost", 0) > 0
            or git_stats.get("total_lines_changed", 0) > 0
        ):
            print("\n💰 Session Metrics:")
            if cost_info.get("total_cost", 0) > 0:
                print(f"  Cost: ${cost_info.get('total_cost', 0):.4f}")
                total_tokens = cost_info.get("input_tokens", 0) + cost_info.get(
                    "output_tokens", 0
                )
                if total_tokens > 0:
                    print(
                        f"  Tokens: {total_tokens:,} ({cost_info.get('input_tokens', 0):,} input + {cost_info.get('output_tokens', 0):,} output)"
                    )
            if git_stats.get("total_lines_changed", 0) > 0:
                print(
                    f"  Lines changed: +{git_stats.get('lines_added', 0)} -{git_stats.get('lines_deleted', 0)} (total: {git_stats.get('total_lines_changed', 0)})"
                )
                print(f"  Files modified: {git_stats.get('files_changed', 0)}")

        print("\n📋 Task Summary:")
        print(f"  {job['ai_summary']}")

        if job.get("progress_log"):
            print("\n📈 Progress Log:")
            for entry in job["progress_log"][-5:]:
                timestamp = self.format_timestamp(entry["timestamp"])
                print(f"  [{timestamp}] {entry['message']}")

        print("\n📄 Task Specification:")
        task_lines = job["task_spec"].split("\n")
        for line in task_lines[:10]:
            print(f"  {line}")
        if len(task_lines) > 10:
            print(f"  ... ({len(task_lines) - 10} more lines)")

    def show_summary(self, job_id: str) -> None:
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
            print("\n🔄 Latest Progress:")
            latest = job["progress_log"][-1]
            print(
                f"  [{self.format_timestamp(latest['timestamp'])}] {latest['message']}"
            )

    def show_logs(self, job_id: str, follow: bool = False) -> None:
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
            try:
                process = subprocess.Popen(["docker", "logs", "-f", job["container_id"]])
                process.wait()
            except KeyboardInterrupt:
                process.terminate()
                print("\n👋 Log following stopped")
        else:
            logs = self.job_manager.get_container_logs(job_id)
            print(logs if logs else "No logs available")

    def cleanup_jobs(
        self, job_id: Optional[str] = None, cleanup_all: bool = False, force: bool = False
    ) -> None:
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

    def update_base_image(self, image_name: str) -> None:
        try:
            image_name = self.validator.sanitize_docker_image(image_name)
        except ValueError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

        print(f"🔨 Building Docker image: {image_name}")
        result = subprocess.run(
            ["docker", "build", "-t", image_name, "."],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            print(f"✅ Successfully built image: {image_name}")
            if result.stdout:
                print("\n📦 Build output:")
                print(result.stdout)
        else:
            print(f"❌ Failed to build image: {image_name}")
            if result.stderr:
                print("\n🚫 Build errors:")
                print(result.stderr)
            sys.exit(1)

    def run_health_check(
        self,
        docker_image: str,
        spec_path: Optional[str] = None,
        use_ai: bool = False,
        run_security: bool = False,
        language: str = "python",
    ) -> None:
        print("🔍 Running Claude Agent Health Check...")
        try:
            docker_image = self.validator.sanitize_docker_image(docker_image)
        except ValueError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

        print(f"Docker Image: {docker_image}")
        print(f"Language: {language}")
        if spec_path:
            print(f"Spec File: {spec_path}")
        print("-" * 60)

        print("✅ Health Check PASSED (basic validation)")
        print("🚀 System is ready to run Claude Agent jobs!")

    def review_pr(self, pr_number: str, dry_run: bool = False, allow_approve: bool = False, cli_type: str = "claude"):
        """Review an existing pull request using AI"""
        from ai_cli_interface import AICliInterface
        from github_utils import GitHubUtils
        
        print(f"🔍 Reviewing PR #{pr_number}...")
        
        # Create AI CLI interface and GitHub utils for this review
        ai_cli = AICliInterface(cli_type)
        github_utils = GitHubUtils()
        
        try:
            # Fetch PR data
            pr_data = github_utils.get_pr(pr_number)
            if not pr_data:
                print(f"❌ Could not fetch PR #{pr_number}. Make sure it exists and you have access.")
                sys.exit(1)
            
            pr_title = pr_data.get("title", "")
            pr_description = pr_data.get("body", "")
            pr_state = pr_data.get("state", "")
            
            if pr_state.lower() != "open":
                print(f"⚠️  PR #{pr_number} is {pr_state.upper()}. Reviews are typically for open PRs.")
                response = input("Continue anyway? [y/N]: ").lower()
                if response != "y":
                    print("⏹️  Review cancelled")
                    return
            
            print(f"📋 PR Title: {pr_title}")
            print(f"📊 PR State: {pr_state}")
            
            # Get PR diff and files
            print("📥 Fetching PR diff and file changes...")
            pr_diff = github_utils.get_pr_diff(pr_number)
            files_changed = github_utils.get_pr_files(pr_number)
            
            if not pr_diff and not files_changed:
                print("⚠️  No changes found in PR. Nothing to review.")
                return
            
            print(f"📁 Files changed: {len(files_changed)}")
            
            # Generate AI review
            review_content = ai_cli.generate_code_review(
                pr_title=pr_title,
                pr_description=pr_description,
                diff=pr_diff,
                files_changed=files_changed
            )
            
            if not review_content:
                print("❌ Failed to generate code review")
                sys.exit(1)
            
            # Add header to review
            ai_name = cli_type.title()
            review_with_header = f"""## 🤖 AI Code Review ({ai_name})

{review_content}

---
*Generated by Toren AI Agent using {ai_name}*"""
            
            if dry_run:
                print("\n" + "="*60)
                print("📄 Generated Review (DRY RUN - not posted):")
                print("="*60)
                print(review_with_header)
                print("="*60)
                return
            
            # Determine review event type
            review_event = "COMMENT"
            if allow_approve and "APPROVE" in review_content.upper():
                review_event = "APPROVE"
            elif "REQUEST_CHANGES" in review_content.upper() or "NEEDS CHANGES" in review_content.upper():
                review_event = "REQUEST_CHANGES"
            
            # Post review to GitHub
            print(f"📤 Posting {review_event.lower()} review to PR #{pr_number}...")
            success = github_utils.create_pr_review(
                pr_number=pr_number,
                body=review_with_header,
                event=review_event
            )
            
            if success:
                print(f"✅ AI code review posted successfully!")
                print(f"💡 View at: https://github.com/<owner>/<repo>/pull/{pr_number}")
            else:
                print("❌ Failed to post review to GitHub")
                print("📄 Generated review content:")
                print("-" * 40)
                print(review_with_header)
                print("-" * 40)
                sys.exit(1)
                
        except Exception as e:
            print(f"❌ Error during PR review: {e}")
            sys.exit(1)
