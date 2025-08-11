#!/usr/bin/env python3
"""
GitHub Utilities for Claude Code Container Execution
Provides simple CLI interface for GitHub API interactions
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

from message_templates import MessageTemplates


class GitHubError(Exception):
    """Base exception for GitHub operations"""


class GitHubAPIError(GitHubError):
    """GitHub API call failed"""

    def __init__(self, message: str, command: Optional[List[str]] = None, exit_code: Optional[int] = None):
        super().__init__(message)
        self.command = command
        self.exit_code = exit_code


class GitHubDataError(GitHubError):
    """GitHub data parsing/validation failed"""


class GitHubAuthError(GitHubError):
    """GitHub authentication failed"""


class GitHubUtils:
    def __init__(self, default_reviewer: str = "vikranth22446"):
        self.default_reviewer = default_reviewer

    def run_gh_command(self, cmd: list) -> str:
        """Run gh CLI command and return output, raising GitHubError on failure"""
        full_cmd = ["gh"] + cmd
        try:
            result = subprocess.run(
                full_cmd, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if (
                "authentication" in e.stderr.lower()
                or "unauthorized" in e.stderr.lower()
            ):
                raise GitHubAuthError(
                    MessageTemplates.GITHUB_AUTH_FAILED.format(error=e.stderr.strip())
                )

            if e.returncode == 4:
                raise GitHubAPIError(
                    MessageTemplates.GITHUB_RESOURCE_NOT_FOUND,
                    command=full_cmd,
                    exit_code=e.returncode,
                )

            raise GitHubAPIError(
                f"GitHub CLI command failed: {e.stderr.strip()}",
                command=full_cmd,
                exit_code=e.returncode,
            )

    def comment_issue(self, issue_number: str, message: str) -> bool:
        """Post comment to GitHub issue"""
        try:
            self.run_gh_command(["issue", "comment", issue_number, "--body", message])
            print(MessageTemplates.github_comment_success("issue", issue_number))
            return True
        except GitHubError as e:
            print(
                MessageTemplates.github_error(
                    "api", f"Failed to comment on issue #{issue_number}: {e}"
                )
            )
            return False

    def comment_pr(self, pr_number: str, message: str) -> bool:
        """Post comment to GitHub PR"""
        try:
            self.run_gh_command(["pr", "comment", pr_number, "--body", message])
            print(MessageTemplates.github_comment_success("PR", pr_number))
            return True
        except GitHubError as e:
            print(
                MessageTemplates.github_error(
                    "api", f"Failed to comment on PR #{pr_number}: {e}"
                )
            )
            return False

    def get_issue(self, issue_number: str) -> Optional[Dict[str, Any]]:
        """Get issue details"""
        try:
            output = self.run_gh_command(
                ["issue", "view", issue_number, "--json", "title,body,number,state"]
            )
            return json.loads(output)
        except GitHubError:
            return None
        except json.JSONDecodeError as e:
            raise GitHubDataError(
                MessageTemplates.ISSUE_DATA_PARSE_ERROR.format(error=str(e))
            )

    def get_pr(self, pr_number: str) -> Optional[Dict[str, Any]]:
        """Get PR details"""
        try:
            output = self.run_gh_command(
                [
                    "pr",
                    "view",
                    pr_number,
                    "--json",
                    "title,body,number,state,headRefName",
                ]
            )
            return json.loads(output)
        except GitHubError:
            return None
        except json.JSONDecodeError as e:
            raise GitHubDataError(
                MessageTemplates.PR_DATA_PARSE_ERROR.format(error=str(e))
            )

    def get_pr_comments(self, pr_number: str) -> List[Dict[str, Any]]:
        """Get PR comments, filtered for @claude mentions"""
        try:
            output = self.run_gh_command(
                ["api", f"repos/:owner/:repo/issues/{pr_number}/comments"]
            )
            all_comments = json.loads(output)

            # Filter for @claude mentions
            comments = []
            for comment in all_comments:
                body = comment.get("body", "")
                if "@claude" in body.lower():
                    comments.append(
                        {
                            "id": comment.get("id"),
                            "body": body,
                            "user": comment.get("user", {}).get("login"),
                            "created_at": comment.get("created_at"),
                            "updated_at": comment.get("updated_at"),
                        }
                    )
            return comments
        except (GitHubError, json.JSONDecodeError):
            return []

    def get_pr_diff(self, pr_number: str) -> str:
        """Get unified diff for PR"""
        try:
            output = self.run_gh_command(
                ["pr", "diff", pr_number]
            )
            return output
        except GitHubError:
            return ""

    def get_pr_files(self, pr_number: str) -> List[Dict[str, Any]]:
        """Get list of files changed in PR"""
        try:
            output = self.run_gh_command(
                ["api", f"repos/:owner/:repo/pulls/{pr_number}/files"]
            )
            return json.loads(output)
        except (GitHubError, json.JSONDecodeError):
            return []

    def create_pr_review(self, pr_number: str, body: str, event: str = "COMMENT") -> bool:
        """Create a PR review with comments"""
        import tempfile
        
        try:
            # First, get the latest commit SHA for the PR
            pr_data = self.run_gh_command([
                "api", f"repos/:owner/:repo/pulls/{pr_number}",
                "--jq", ".head.sha"
            ])
            commit_sha = pr_data.strip().strip('"')
            
            if not commit_sha:
                print(f"❌ Could not get commit SHA for PR #{pr_number}")
                return False
            
            # Prepare review data as JSON
            review_data = {
                "body": body,
                "event": event,
                "commit_id": commit_sha
            }
            
            # Create temporary file with JSON data
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(review_data, f, ensure_ascii=False, indent=2)
                temp_file = f.name
            
            
            try:
                # Create review using gh api with JSON input
                self.run_gh_command([
                    "api", 
                    f"repos/:owner/:repo/pulls/{pr_number}/reviews",
                    "--method", "POST",
                    "--input", temp_file
                ])
                
                print(f"✅ Successfully posted code review to PR #{pr_number}")
                return True
            finally:
                # Clean up temporary file
                import os
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass
                    
        except GitHubError as e:
            print(f"❌ Failed to create PR review: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error creating PR review: {e}")
            return False

    def extract_claude_tasks_from_pr(self, pr_number: str) -> str:
        """Extract tasks for Claude from PR comments and description"""
        pr_data = self.get_pr(pr_number)
        if not pr_data:
            return MessageTemplates.UNABLE_TO_FETCH_PR

        comments = self.get_pr_comments(pr_number)

        # Build comprehensive task specification
        task_spec = MessageTemplates.pr_task_header(
            pr_number,
            pr_data.get("title", "Unknown"),
            pr_data.get("state", "unknown"),
            pr_data.get("headRefName", "unknown"),
            pr_data.get("body", "No description available"),
        )

        if comments:
            # Sort by creation date, newest first
            sorted_comments = sorted(
                comments, key=lambda x: x.get("created_at", ""), reverse=True
            )

            for comment in sorted_comments[:5]:  # Limit to last 5 relevant comments
                user = comment.get("user", "Unknown")
                created = comment.get("created_at", "")
                body = comment.get("body", "")
                task_spec += MessageTemplates.pr_task_comment(user, created, body)
        else:
            task_spec += MessageTemplates.PR_TASK_NO_COMMENTS

        task_spec += MessageTemplates.PR_TASK_INSTRUCTIONS

        return task_spec

    def update_status(self, message: str, issue_number: Optional[str] = None) -> bool:
        """Post status update to issue or as general comment"""
        status_msg = MessageTemplates.status_update(message)

        if issue_number:
            return self.comment_issue(issue_number, status_msg)
        else:
            if "GITHUB_ISSUE_NUMBER" in os.environ:
                return self.comment_issue(os.environ["GITHUB_ISSUE_NUMBER"], status_msg)
            elif "PR_NUMBER" in os.environ:
                return self.comment_pr(os.environ["PR_NUMBER"], status_msg)
            else:
                print(MessageTemplates.STATUS_FALLBACK.format(message=message))
                return True

    def notify_progress(
        self, step: str, details: str = "", issue_number: Optional[str] = None
    ) -> bool:
        """Post progress update"""
        progress_msg = MessageTemplates.progress_update(step, details)
        return self.update_status(progress_msg, issue_number)

    def notify_completion(
        self,
        summary: str,
        reviewer: Optional[str] = None,
        issue_number: Optional[str] = None,
    ) -> bool:
        """Post completion notification with cost information"""
        reviewer_tag = reviewer or self.default_reviewer
        cost_info_str = self._get_cost_info_for_comment()
        completion_msg = MessageTemplates.completion_notification(
            reviewer_tag, summary, cost_info_str
        )
        return self.update_status(completion_msg, issue_number)

    def _get_cost_info_for_comment(self) -> str:
        """Get formatted cost information for GitHub comments"""
        try:
            import json
            from pathlib import Path

            # Try to load cost information from the shared location
            cost_file = Path("/tmp/cost_data/session_cost.json")
            if cost_file.exists():
                with open(cost_file, "r") as f:
                    session_data = json.load(f)

                summary = session_data.get("summary", {})
                cost = summary.get("total_cost", 0.0)
                tokens = summary.get("total_tokens", 0)
                lines = summary.get("lines_changed", 0)
                files = summary.get("files_changed", 0)

                if cost > 0 or lines > 0:
                    cost_lines = []
                    if cost > 0:
                        cost_lines.append(f"💰 **Cost**: ${cost:.4f}")
                    if tokens > 0:
                        cost_lines.append(f"🔤 **Tokens**: {tokens:,}")
                    if lines > 0:
                        cost_lines.append(f"📝 **Lines Changed**: {lines}")
                    if files > 0:
                        cost_lines.append(f"📁 **Files Modified**: {files}")

                    return "\n" + "\n".join(cost_lines) + "\n"
        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as e:
            # Cost info not available or malformed - this is expected in many cases
            print(f"ℹ️ Cost information unavailable: {type(e).__name__}")
        except PermissionError:
            print("⚠️ Permission denied accessing cost data")

        return ""

    def notify_error(
        self,
        error: str,
        reviewer: Optional[str] = None,
        issue_number: Optional[str] = None,
    ) -> bool:
        """Post error notification"""
        reviewer_tag = reviewer or self.default_reviewer
        error_msg = MessageTemplates.error_notification(reviewer_tag, error)
        return self.update_status(error_msg, issue_number)

    def request_clarification(
        self, question: str, issue_number: Optional[str] = None
    ) -> bool:
        """Ask for clarification on issue"""
        clarification_msg = MessageTemplates.clarification_request(question)
        return self.update_status(clarification_msg, issue_number)

    def commit_and_push(self, branch_name: str, task_summary: str) -> bool:
        """Commit changes and push to remote"""
        try:
            # Add all changes
            subprocess.run(["git", "add", "."], check=True)

            # Commit with message
            commit_msg = MessageTemplates.commit_message(task_summary)
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)

            # Push branch
            subprocess.run(["git", "push", "-u", "origin", branch_name], check=True)
            print(MessageTemplates.COMMIT_PUSH_SUCCESS.format(branch_name=branch_name))
            return True

        except subprocess.CalledProcessError as e:
            print(MessageTemplates.COMMIT_PUSH_FAILED.format(error=str(e)))
            return False

    def create_pull_request(
        self,
        title: str,
        summary: str,
        issue_number: Optional[str] = None,
        reviewer: Optional[str] = None,
    ) -> bool:
        """Create pull request with comprehensive description"""
        reviewer_name = reviewer or self.default_reviewer
        cost_info_str = self._get_cost_info_for_comment()

        # Build issue reference
        issue_ref = ""
        if issue_number:
            # Extract just the number if it's a full URL
            if "github.com" in issue_number:
                issue_num = issue_number.split("/")[-1]
            else:
                issue_num = issue_number.replace("#", "")
            issue_ref = f"\nCloses #{issue_num}"

        pr_body = MessageTemplates.pr_body(
            summary, reviewer_name, cost_info_str, issue_ref
        )

        try:
            output = self.run_gh_command(
                ["pr", "create", "--title", title, "--body", pr_body]
            )
            pr_url = output.strip()
            print(MessageTemplates.PR_CREATED_SUCCESS.format(pr_url=pr_url))
            return True
        except GitHubError as e:
            print(MessageTemplates.PR_CREATE_FAILED.format(output=str(e)))
            return False


def main():
    parser = argparse.ArgumentParser(description="GitHub Utilities for Claude Code")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Comment commands
    comment_issue_parser = subparsers.add_parser(
        "comment-issue", help="Comment on GitHub issue"
    )
    comment_issue_parser.add_argument("issue_number", help="Issue number")
    comment_issue_parser.add_argument("message", help="Comment message")

    comment_pr_parser = subparsers.add_parser("comment-pr", help="Comment on GitHub PR")
    comment_pr_parser.add_argument("pr_number", help="PR number")
    comment_pr_parser.add_argument("message", help="Comment message")

    # Get commands
    get_issue_parser = subparsers.add_parser("get-issue", help="Get issue details")
    get_issue_parser.add_argument("issue_number", help="Issue number")

    get_pr_parser = subparsers.add_parser("get-pr", help="Get PR details")
    get_pr_parser.add_argument("pr_number", help="PR number")

    # Status commands
    status_parser = subparsers.add_parser("update-status", help="Post status update")
    status_parser.add_argument("message", help="Status message")
    status_parser.add_argument("--issue", help="Issue number (optional)")

    progress_parser = subparsers.add_parser(
        "notify-progress", help="Post progress update"
    )
    progress_parser.add_argument("step", help="Current step")
    progress_parser.add_argument("--details", default="", help="Additional details")
    progress_parser.add_argument("--issue", help="Issue number (optional)")

    completion_parser = subparsers.add_parser(
        "notify-completion", help="Post completion notification"
    )
    completion_parser.add_argument("summary", help="Task summary")
    completion_parser.add_argument("--reviewer", help="Reviewer username")
    completion_parser.add_argument("--issue", help="Issue number (optional)")

    error_parser = subparsers.add_parser("notify-error", help="Post error notification")
    error_parser.add_argument("error", help="Error description")
    error_parser.add_argument("--reviewer", help="Reviewer username")
    error_parser.add_argument("--issue", help="Issue number (optional)")

    clarification_parser = subparsers.add_parser(
        "request-clarification", help="Request clarification"
    )
    clarification_parser.add_argument("question", help="Question to ask")
    clarification_parser.add_argument("--issue", help="Issue number (optional)")

    pr_parser = subparsers.add_parser("create-pr", help="Create pull request")
    pr_parser.add_argument("title", help="PR title")
    pr_parser.add_argument("summary", help="PR summary description")
    pr_parser.add_argument("--issue", help="Issue number to close (optional)")
    pr_parser.add_argument("--reviewer", help="Reviewer username")

    pr_comments_parser = subparsers.add_parser(
        "get-pr-comments", help="Get PR comments mentioning @claude"
    )
    pr_comments_parser.add_argument("pr_number", help="PR number")

    pr_tasks_parser = subparsers.add_parser(
        "extract-pr-tasks", help="Extract tasks from PR comments"
    )
    pr_tasks_parser.add_argument("pr_number", help="PR number")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    utils = GitHubUtils()
    success = True

    if args.command == "comment-issue":
        success = utils.comment_issue(args.issue_number, args.message)
    elif args.command == "comment-pr":
        success = utils.comment_pr(args.pr_number, args.message)
    elif args.command == "get-issue":
        issue = utils.get_issue(args.issue_number)
        if issue:
            print(json.dumps(issue, indent=2))
        else:
            success = False
    elif args.command == "get-pr":
        pr = utils.get_pr(args.pr_number)
        if pr:
            print(json.dumps(pr, indent=2))
        else:
            success = False
    elif args.command == "update-status":
        success = utils.update_status(args.message, args.issue)
    elif args.command == "notify-progress":
        success = utils.notify_progress(args.step, args.details, args.issue)
    elif args.command == "notify-completion":
        success = utils.notify_completion(args.summary, args.reviewer, args.issue)
    elif args.command == "notify-error":
        success = utils.notify_error(args.error, args.reviewer, args.issue)
    elif args.command == "request-clarification":
        success = utils.request_clarification(args.question, args.issue)
    elif args.command == "create-pr":
        success = utils.create_pull_request(
            args.title, args.summary, args.issue, args.reviewer
        )
    elif args.command == "get-pr-comments":
        comments = utils.get_pr_comments(args.pr_number)
        if comments:
            print(json.dumps(comments, indent=2))
            success = True
        else:
            print(MessageTemplates.NO_CLAUDE_MENTIONS)
            success = False
    elif args.command == "extract-pr-tasks":
        task_spec = utils.extract_claude_tasks_from_pr(args.pr_number)
        print(task_spec)
        success = True

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
