#!/usr/bin/env python3
"""
AI CLI execution module - Provider-agnostic AI assistant runner
"""

import argparse
import glob
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional


class AIProviderConfig:
    def __init__(self, config_dir: str = "/usr/local/etc/container"):
        self.config_dir = Path(config_dir)
        self._load_configs()

    def _load_configs(self):
        """Load provider and language configurations"""
        try:
            with open(self.config_dir / "ai_providers.json") as f:
                self.providers = json.load(f)
        except FileNotFoundError:
            self.providers = self._default_providers()

        try:
            with open(self.config_dir / "languages.json") as f:
                self.languages = json.load(f)
        except FileNotFoundError:
            self.languages = self._default_languages()

    def _default_providers(self) -> Dict[str, Any]:
        return {
            "claude": {
                "command": "claude",
                "args": ["--dangerously-skip-permissions"],
                "env_vars": ["IS_SANDBOX=1"],
                "log_pattern": "/root/.claude/projects/*.jsonl",
                "pricing": {"input": 0.000003, "output": 0.000015},
            },
            "gpt": {
                "command": "gpt-cli",
                "args": [],
                "env_vars": [],
                "log_pattern": "/tmp/gpt_logs/*.json",
                "pricing": {"input": 0.000005, "output": 0.000015},
            },
        }

    def _default_languages(self) -> Dict[str, Any]:
        return {
            "python": {
                "tools": "bandit -r . (security), safety check (vulnerabilities), pip-audit (dependencies)"
            },
            "rust": {
                "tools": "cargo-audit (vulnerabilities), cargo clippy (lints), rust-security-scan (combined)"
            },
            "javascript": {"tools": "eslint (linting), audit-ci (dependencies)"},
        }


class AIExecutor:
    def __init__(self, provider: str, config: AIProviderConfig):
        self.provider = provider
        self.config = config
        self.provider_config = config.providers.get(
            provider, config.providers["claude"]
        )

    def build_prompt(
        self, task_spec: str, branch: str, base_branch: str, language: str
    ) -> str:
        """Build optimized prompt for the AI provider"""

        # Get language-specific tools info
        lang_config = self.config.languages.get(
            language, self.config.languages["python"]
        )
        security_tools = lang_config.get("tools", "Security tools available")

        # Build workflow instructions
        git_workflow = f"""git add . && git commit -m "Auto-fix: [summary]

Co-authored-by: {os.environ.get('DEFAULT_REVIEWER', 'vikranth22446')} <{os.environ.get('DEFAULT_REVIEWER', 'vikranth22446')}@users.noreply.github.com>" && git push -u origin {branch}"""

        # PR workflow
        pr_number = os.environ.get("PR_NUMBER")
        github_issue = os.environ.get("GITHUB_ISSUE_NUMBER", "")
        issue_arg = f"--issue {github_issue}" if github_issue else ""

        if pr_number:
            pr_workflow = f"""Working on existing PR {pr_number}:
1. First review ALL changes made in this PR so far: git diff {base_branch}...{branch}
2. After completing work, push changes and comment on PR:
python /usr/local/bin/github_utils.py comment-pr {pr_number} "✅ **Work Complete**

[Summary of changes made]

Please review the additional changes.\""""
        else:
            pr_workflow = f"""After completing work, create PR:
python /usr/local/bin/github_utils.py create-pr "Fix: [brief title]" "[detailed summary]" {issue_arg} --reviewer {os.environ.get('DEFAULT_REVIEWER', 'vikranth22446')}"""

        return f"""Complete task in {task_spec}. Git ready: branch {branch} (base: {base_branch}).

{git_workflow}

IMPORTANT: After making all changes, ALWAYS:
1. Run 'git status' to verify all intended files are committed
2. Run 'git log --oneline -1' to confirm your commit was successful
3. Remove any temporary scratch work files that are not needed for the final solution

Tool Execution Guide: DO NOT execute docker commands in containerized environments (docker-in-docker issues) - only read/modify files unless explicitly requested

{pr_workflow}

It is vital that updates are posted based on the progress. Post updates via:
- python /usr/local/bin/github_utils.py notify-progress "step"
- python /usr/local/bin/github_utils.py notify-completion "summary" --reviewer {os.environ.get('DEFAULT_REVIEWER', 'vikranth22446')}

{security_tools}

Use /tmp/claude_docs/ for analysis. Working dir: /workspace."""

    def execute(
        self, task_spec: str, branch: str, base_branch: str, language: str
    ) -> int:
        """Execute the AI provider with the given task"""

        prompt = self.build_prompt(task_spec, branch, base_branch, language)

        # Build command
        cmd = (
            [self.provider_config["command"]] + self.provider_config["args"] + [prompt]
        )

        # Setup environment
        env = os.environ.copy()
        for env_var in self.provider_config["env_vars"]:
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                env[key] = value

        print(f"🤖 Starting {self.provider} execution...", flush=True)
        
        # Post task started notification to GitHub
        self._post_task_started(task_spec, branch)

        # Start AI process with real-time output streaming
        process = subprocess.Popen(
            cmd, 
            env=env
        )

        # Start log monitoring
        log_monitor = LogMonitor(
            self.provider_config["log_pattern"],
            self.provider_config["pricing"],
            self.provider,
        )
        log_monitor.start()

        # Wait for completion and get exit code
        exit_code = process.wait()
        log_monitor.stop()
        
        # Post completion/failure notification to GitHub
        self._post_task_completion(exit_code, branch)

        return exit_code


class LogMonitor:
    """Monitor AI provider logs and extract useful information"""

    def __init__(
        self, log_pattern: str, pricing: Dict[str, float], provider: str = "claude"
    ):
        self.log_pattern = log_pattern
        self.pricing = pricing
        self.provider = provider
        self.running = False
        self.log_thread = None
        self.cost_monitor = None
        self.cost_monitor_file = "/usr/local/container/lib/cost_monitor.py"

    def start(self):
        """Start log monitoring in background"""
        self.running = True

        # Initialize cost monitoring
        if not os.path.exists("/tmp/claude_cost_data.json"):
            subprocess.run(
                ["python3", self.cost_monitor_file, "--initialize"],
                check=False,
            )

        print("📋 Setting up log streaming...", flush=True)

        if self.provider == "claude":
            self.log_thread = threading.Thread(target=self._monitor_claude_logs)
            self.log_thread.daemon = True
            self.log_thread.start()
        else:
            print(f"📋 Generic log monitoring for {self.provider}", flush=True)

    def _find_claude_log_file(self, timeout: int = 40) -> Optional[str]:
        """Find Claude's JSONL log file with timeout"""
        for i in range(timeout):
            time.sleep(1)
            log_files = glob.glob("/root/.claude/projects/**/*.jsonl", recursive=True)
            if log_files:
                log_file = log_files[0]  # Take the first/newest
                print(f"📋 Found Claude log file after {i + 1} seconds: {log_file}", flush=True)
                return log_file

            if (i + 1) % 10 == 0:
                print(f"📋 Still waiting for Claude log file... ({i + 1}s)", flush=True)

        print("⚠️  Could not find Claude log file for streaming", flush=True)
        return None

    def _monitor_claude_logs(self):
        """Monitor and parse Claude's JSONL logs"""
        log_file = self._find_claude_log_file()
        if not log_file:
            return

        print(f"📋 Streaming Claude logs from: {log_file}", flush=True)

        try:
            # Follow the log file like tail -f
            with open(log_file, "r") as f:
                # Skip to end of file
                f.seek(0, 2)

                while self.running:
                    line = f.readline()
                    if line:
                        self._parse_claude_log_line(line.strip())
                    else:
                        time.sleep(0.1)  # Wait for new content
        except Exception as e:
            print(f"❌ Log monitoring error: {e}", flush=True)

    def _parse_claude_log_line(self, line: str):
        """Parse a single Claude JSONL log line"""
        try:
            if not line:
                return

            data = json.loads(line)

            # Handle new Claude Code JSONL format
            if "message" in data and data.get("type"):
                msg = data["message"]
                msg_type = data.get("type")

                if msg_type == "assistant":
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if item.get("type") == "text":
                                text = item.get("text", "")
                                if text and len(text.strip()) > 0:
                                    print(f"🤖 Claude: {text}", flush=True)
                            elif item.get("type") == "tool_use":
                                self._format_tool_use(item)

                    # Handle usage info and update costs
                    usage = msg.get("usage", {})
                    if usage:
                        input_tokens = usage.get("input_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0)
                        if input_tokens > 0 or output_tokens > 0:
                            print(f"💰 Tokens: {input_tokens} in, {output_tokens} out", flush=True)

                            # Update cost tracking
                            subprocess.run(
                                [
                                    "python3",
                                    self.cost_monitor_file, 
                                    "--update",
                                    "--input-tokens",
                                    str(input_tokens),
                                    "--output-tokens",
                                    str(output_tokens),
                                ],
                                check=False,
                            )

                elif msg_type == "user":
                    # Handle tool results
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if item.get("type") == "tool_result":
                                result = item.get("content", "")
                                self._format_tool_result(result)

        except Exception:
            # Only show error-related lines
            if line and any(
                keyword in line.lower() for keyword in ["error", "failed", "exception"]
            ):
                print(f"❌ {line[:200]}..." if len(line) > 200 else f"❌ {line}")

    def _format_tool_use(self, item: Dict[str, Any]):
        """Format tool use messages for display"""
        tool_name = item.get("name", "unknown")
        tool_input = item.get("input", {})

        if tool_name == "Read":
            file_path = tool_input.get("file_path", "unknown")
            print(f"📖 Reading: {file_path}", flush=True)
        elif tool_name == "Edit":
            file_path = tool_input.get("file_path", "unknown")
            print(f"✏️  Editing: {file_path}", flush=True)
        elif tool_name == "Write":
            file_path = tool_input.get("file_path", "unknown")
            print(f"📝 Writing: {file_path}", flush=True)
        elif tool_name == "Bash":
            desc = tool_input.get("description", "")
            command = tool_input.get("command", "")
            if desc:
                print(f"⚡ Running: {desc}", flush=True)
            else:
                display_cmd = command[:50] + "..." if len(command) > 50 else command
                print(f"⚡ Command: {display_cmd}", flush=True)
        elif tool_name == "TodoWrite":
            print("📝 Updated todo list", flush=True)
        elif tool_name == "Grep":
            pattern = tool_input.get("pattern", "")
            print(f"🔍 Searching for: {pattern}", flush=True)
        elif tool_name == "Glob":
            pattern = tool_input.get("pattern", "")
            print(f"🔍 Finding files: {pattern}", flush=True)
        else:
            print(f"🔧 Tool: {tool_name}", flush=True)

    def _format_tool_result(self, result: str):
        """Format tool result messages for display"""
        if result and "error" not in result.lower() and len(result) < 100:
            print(f"🔧 Tool result: {result}", flush=True)
        elif "error" in result.lower():
            print(f"❌ Tool error: {result[:100]}", flush=True)
        else:
            print("🔧 Tool completed successfully", flush=True)

    def stop(self):
        """Stop log monitoring"""
        self.running = False
        if self.log_thread and self.log_thread.is_alive():
            self.log_thread.join(timeout=1.0)
        print("📋 Log monitoring stopped")


def main():
    parser = argparse.ArgumentParser(description="AI Provider Executor")
    parser.add_argument("--provider", default="claude", help="AI provider to use")
    parser.add_argument("--task-spec", required=True, help="Path to task specification")
    parser.add_argument("--branch", required=True, help="Git branch name")
    parser.add_argument("--base-branch", required=True, help="Base git branch")
    parser.add_argument("--language", default="python", help="Programming language")
    parser.add_argument("--starting-commit", help="Starting commit hash")

    args = parser.parse_args()

    config = AIProviderConfig()
    executor = AIExecutor(args.provider, config)

    exit_code = executor.execute(
        args.task_spec, args.branch, args.base_branch, args.language
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
