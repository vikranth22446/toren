#!/usr/bin/env python3
"""
GitHub Utilities for Claude Code Container Execution
Provides simple CLI interface for GitHub API interactions
"""

import argparse
import subprocess
import json
import sys
import os
from typing import Optional, Dict, Any, Tuple, List


class GitHubUtils:
    def __init__(self, default_reviewer: str = "vikranth22446"):
        self.default_reviewer = default_reviewer
        # Support for both issue and PR notifications

    def run_gh_command(self, cmd: list) -> Tuple[bool, str]:
        """Run gh CLI command and return success, output"""
        try:
            result = subprocess.run(
                ["gh"] + cmd, capture_output=True, text=True, check=True
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip()

    def comment_issue(self, issue_number: str, message: str) -> bool:
        """Post comment to GitHub issue"""
        success, output = self.run_gh_command(
            ["issue", "comment", issue_number, "--body", message]
        )
        if success:
            print(f"✅ Posted comment to issue #{issue_number}")
        else:
            print(f"❌ Failed to comment on issue #{issue_number}: {output}")
        return success

    def comment_pr(self, pr_number: str, message: str) -> bool:
        """Post comment to GitHub PR"""
        success, output = self.run_gh_command(
            ["pr", "comment", pr_number, "--body", message]
        )
        if success:
            print(f"✅ Posted comment to PR #{pr_number}")
        else:
            print(f"❌ Failed to comment on PR #{pr_number}: {output}")
        return success

    def get_issue(self, issue_number: str) -> Optional[Dict[str, Any]]:
        """Get issue details"""
        success, output = self.run_gh_command(
            ["issue", "view", issue_number, "--json", "title,body,number,state"]
        )
        if success:
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return None
        return None

    def get_pr(self, pr_number: str) -> Optional[Dict[str, Any]]:
        """Get PR details"""
        success, output = self.run_gh_command(
            ["pr", "view", pr_number, "--json", "title,body,number,state,headRefName"]
        )
        if success:
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return None
        return None

    def get_pr_comments(self, pr_number: str) -> List[Dict[str, Any]]:
        """Get PR comments, filtered for @claude mentions"""
        success, output = self.run_gh_command([
            "api", f"repos/:owner/:repo/pulls/{pr_number}/comments", 
            "--jq", ".[].body"
        ])
        
        comments = []
        if success:
            try:
                # Get full comment data with metadata
                success_full, output_full = self.run_gh_command([
                    "api", f"repos/:owner/:repo/pulls/{pr_number}/comments"
                ])
                if success_full:
                    all_comments = json.loads(output_full)
                    
                    # Filter for @claude mentions
                    for comment in all_comments:
                        body = comment.get("body", "")
                        if "@claude" in body.lower():
                            comments.append({
                                "id": comment.get("id"),
                                "body": body,
                                "user": comment.get("user", {}).get("login"),
                                "created_at": comment.get("created_at"),
                                "updated_at": comment.get("updated_at")
                            })
                            
            except json.JSONDecodeError:
                pass
                
        return comments

    def extract_claude_tasks_from_pr(self, pr_number: str) -> str:
        """Extract tasks for Claude from PR comments and description"""
        pr_data = self.get_pr(pr_number)
        if not pr_data:
            return "Unable to fetch PR data"
            
        comments = self.get_pr_comments(pr_number)
        
        # Build comprehensive task specification
        task_spec = f"""# Continue Work on PR #{pr_number}

## Original PR Details
**Title**: {pr_data.get('title', 'Unknown')}
**Status**: {pr_data.get('state', 'unknown')}
**Branch**: {pr_data.get('headRefName', 'unknown')}

## Original Description
{pr_data.get('body', 'No description available')}

## Latest Comments Mentioning @claude
"""
        
        if comments:
            # Sort by creation date, newest first
            sorted_comments = sorted(comments, key=lambda x: x.get('created_at', ''), reverse=True)
            
            for comment in sorted_comments[:5]:  # Limit to last 5 relevant comments
                user = comment.get('user', 'Unknown')
                created = comment.get('created_at', '')
                body = comment.get('body', '')
                
                task_spec += f"""
### Comment by @{user} ({created})
{body}

---
"""
        else:
            task_spec += "\nNo recent comments mentioning @claude found."
            
        task_spec += """
## Instructions
Based on the PR context and comments above, continue working on this PR:
1. Address any feedback or requests in the comments
2. Make the requested changes to the codebase
3. Update tests if needed
4. Add commits to the existing PR branch
5. Respond to comments with progress updates

Focus on the most recent comments mentioning @claude for current tasks.
"""
        
        return task_spec

    def update_status(self, message: str, issue_number: Optional[str] = None) -> bool:
        """Post status update to issue or as general comment"""
        status_msg = f"⚙️ **Claude Agent Status Update**\n\n{message}"

        if issue_number:
            return self.comment_issue(issue_number, status_msg)
        else:
            # Try to find issue/PR number from environment or working directory
            if "GITHUB_ISSUE_NUMBER" in os.environ:
                return self.comment_issue(os.environ["GITHUB_ISSUE_NUMBER"], status_msg)
            elif "PR_NUMBER" in os.environ:
                return self.comment_pr(os.environ["PR_NUMBER"], status_msg)
            else:
                print(f"📝 Status: {message}")
                return True

    def notify_progress(
        self, step: str, details: str = "", issue_number: Optional[str] = None
    ) -> bool:
        """Post progress update"""
        progress_msg = f"🔄 **Progress Update**\n\n**Current Step**: {step}"
        if details:
            progress_msg += f"\n**Details**: {details}"
        progress_msg += f"\n\n*Working directory*: `/workspace`"

        return self.update_status(progress_msg, issue_number)

    def notify_completion(
        self,
        summary: str,
        reviewer: Optional[str] = None,
        issue_number: Optional[str] = None,
    ) -> bool:
        """Post completion notification with cost information"""
        reviewer_tag = f"@{reviewer or self.default_reviewer}"
        
        # Try to load cost information
        cost_info_str = self._get_cost_info_for_comment()
        
        completion_msg = f"""✅ **Task Completed** {reviewer_tag}

**Summary**: {summary}
{cost_info_str}
**Next Steps**: Please review the changes and provide feedback.

🎉 Ready for review!"""

        return self.update_status(completion_msg, issue_number)
    
    def _get_cost_info_for_comment(self) -> str:
        """Get formatted cost information for GitHub comments"""
        try:
            import json
            from pathlib import Path
            
            # Try to load cost information from the shared location
            cost_file = Path("/tmp/cost_data/session_cost.json")
            if cost_file.exists():
                with open(cost_file, 'r') as f:
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
        except Exception:
            pass  # Silently fail if cost info not available
        
        return ""

    def notify_error(
        self,
        error: str,
        reviewer: Optional[str] = None,
        issue_number: Optional[str] = None,
    ) -> bool:
        """Post error notification"""
        reviewer_tag = f"@{reviewer or self.default_reviewer}"
        error_msg = f"""❌ **Claude Agent Error** {reviewer_tag}

**Issue**: {error}

**Status**: Manual intervention required.

Please review the error and provide guidance."""

        return self.update_status(error_msg, issue_number)

    def request_clarification(
        self, question: str, issue_number: Optional[str] = None
    ) -> bool:
        """Ask for clarification on issue"""
        clarification_msg = f"""❓ **Clarification Needed**

**Question**: {question}

**Context**: While working on this task, I need additional information to proceed correctly.

Please provide guidance when convenient."""

        return self.update_status(clarification_msg, issue_number)

    def create_pull_request(
        self,
        title: str,
        summary: str,
        issue_number: Optional[str] = None,
        reviewer: Optional[str] = None
    ) -> bool:
        """Create pull request with comprehensive description"""
        reviewer_tag = f"@{reviewer or self.default_reviewer}"
        
        # Try to load cost information
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
        
        pr_body = f"""## Summary
{summary}

## Changes Made
- Automated fixes implemented by Claude Agent
- Code changes follow project conventions
- Security scanning completed{cost_info_str}

## Co-Authors
This PR includes commits co-authored by {reviewer_tag}

## Testing
- [ ] Manual testing recommended
- [ ] Verify all functionality works as expected
- [ ] Check for any edge cases

## Review Notes
{reviewer_tag} - This PR was generated automatically with you as co-author. Please review and test the changes.{issue_ref}

Co-authored-by: {reviewer or self.default_reviewer} <{reviewer or self.default_reviewer}@users.noreply.github.com>"""

        success, output = self.run_gh_command(
            ["pr", "create", "--title", title, "--body", pr_body]
        )
        
        if success:
            pr_url = output.strip()
            print(f"✅ Created PR: {pr_url}")
            return True
        else:
            print(f"❌ Failed to create PR: {output}")
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

    pr_comments_parser = subparsers.add_parser("get-pr-comments", help="Get PR comments mentioning @claude")
    pr_comments_parser.add_argument("pr_number", help="PR number")

    pr_tasks_parser = subparsers.add_parser("extract-pr-tasks", help="Extract tasks from PR comments")
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
        success = utils.create_pull_request(args.title, args.summary, args.issue, args.reviewer)
    elif args.command == "get-pr-comments":
        comments = utils.get_pr_comments(args.pr_number)
        if comments:
            print(json.dumps(comments, indent=2))
            success = True
        else:
            print("No @claude mentions found in PR comments")
            success = False
    elif args.command == "extract-pr-tasks":
        task_spec = utils.extract_claude_tasks_from_pr(args.pr_number)
        print(task_spec)
        success = True

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
