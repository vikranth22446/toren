#!/usr/bin/env python3

import fcntl
import hashlib
import os
import shlex
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional


class ContainerManager:
    # Timeout constants (in seconds)
    DOCKER_BUILD_TIMEOUT = 300  # 5 minutes for Docker builds

    def __init__(self, validator=None):
        self.validator = validator

    def _is_safe_env_var(self, env_var: str) -> bool:
        """Basic safety check for environment variables when no validator is available"""
        if not env_var or "=" not in env_var:
            return False

        # Check for command injection patterns
        dangerous_patterns = [";", "`", "$", "\n", "$(", "${", "|", "&", "\\"]
        return not any(pattern in env_var for pattern in dangerous_patterns)

    def _is_safe_input(self, input_str: str) -> bool:
        """Basic safety check for general inputs"""
        if not input_str:
            return False

        # No dangerous characters that could break shell/docker commands
        dangerous_chars = [";", "`", "$", "\n", "\r", "|", "&", ">", "<"]
        return not any(char in input_str for char in dangerous_chars)

    def _get_cli_install_section(self, cli_type: str) -> str:
        """Generate CLI installation section based on cli_type"""
        if cli_type == "gemini":
            return """RUN npm install -g @google/generative-ai-cli && \\
    echo "Gemini CLI installed" && \\
    # Create gemini config directory
    mkdir -p /root/.config/gemini"""
        elif cli_type == "codex":
            return """RUN npm install -g @openai/codex && \\
    echo "Codex CLI installed\""""
        else:  # default to claude
            return """RUN curl -fsSL https://claude.ai/install.sh | bash && \\
    # Remove any default .claude.json created during installation
    rm -f /root/.claude.json /root/.claude/settings.json 2>/dev/null || true && \\
    echo "Claude CLI installed - default config removed to preserve user mounts\""""

    def generate_agent_dockerfile(
        self, base_image: str, cli_type: str = "claude"
    ) -> str:
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
        chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \\
        echo "deb [arch=\\$$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \\
        apt-get update && apt-get install -y gh; \\
    else \\
        curl -fsSL https://github.com/cli/cli/releases/download/v2.40.1/gh_2.40.1_linux_amd64.tar.gz | \\
        tar -xz -C /tmp && \\
        mv /tmp/gh_2.40.1_linux_amd64/bin/gh /usr/local/bin/gh && \\
        rm -rf /tmp/gh_2.40.1_linux_amd64; \\
    fi

# Install AI CLI based on cli_type
{self._get_cli_install_section(cli_type)}

# Install Python security scanning tools (optional)
COPY security-requirements.txt /tmp/security-requirements.txt
RUN if command -v pip >/dev/null 2>&1; then \\
        pip install -r /tmp/security-requirements.txt || echo "Warning: Failed to install security tools"; \\
    elif command -v pip3 >/dev/null 2>&1; then \\
        pip3 install -r /tmp/security-requirements.txt || echo "Warning: Failed to install security tools"; \\
    fi && \\
    rm /tmp/security-requirements.txt

# Add security scanning utility script
RUN echo '#!/bin/bash' > /usr/local/bin/ai-security-scan && \\
    echo 'echo "🔍 AI Agent Security Scanner"' >> /usr/local/bin/ai-security-scan && \\
    echo 'echo "Available tools:"' >> /usr/local/bin/ai-security-scan && \\
    echo 'command -v bandit >/dev/null && echo "  ✅ bandit - Python security scanner"' >> /usr/local/bin/ai-security-scan && \\
    echo 'command -v safety >/dev/null && echo "  ✅ safety - Dependency vulnerability scanner"' >> /usr/local/bin/ai-security-scan && \\
    echo 'command -v semgrep >/dev/null && echo "  ✅ semgrep - Static analysis security scanner"' >> /usr/local/bin/ai-security-scan && \\
    echo 'echo ""' >> /usr/local/bin/ai-security-scan && \\
    echo 'if [ "$1" = "scan" ]; then' >> /usr/local/bin/ai-security-scan && \\
    echo '    echo "Running bandit security scan on Python files..."' >> /usr/local/bin/ai-security-scan && \\
    echo '    find /workspace -name "*.py" -exec bandit -ll {{}} + 2>/dev/null || echo "No Python files found or bandit failed"' >> /usr/local/bin/ai-security-scan && \\
    echo 'else' >> /usr/local/bin/ai-security-scan && \\
    echo '    echo "Usage: ai-security-scan scan"' >> /usr/local/bin/ai-security-scan && \\
    echo 'fi' >> /usr/local/bin/ai-security-scan && \\
    chmod +x /usr/local/bin/ai-security-scan

# Ensure PATH includes AI CLI tools and Python can import from /usr/local/bin
ENV PATH="/root/.local/bin:$PATH"
ENV PYTHONPATH="/usr/local/bin:$PYTHONPATH"

# Copy refactored container components and GitHub utilities
COPY container/ /usr/local/container/
COPY github_utils.py /usr/local/bin/github_utils.py
COPY message_templates.py /usr/local/bin/message_templates.py
RUN chmod +x /usr/local/container/entrypoint.sh /usr/local/container/lib/*.sh /usr/local/container/lib/*.py /usr/local/bin/github_utils.py /usr/local/bin/message_templates.py

WORKDIR /workspace
ENTRYPOINT ["/usr/local/container/entrypoint.sh"]
"""

    @contextmanager
    def docker_build_lock(self, agent_image: str):
        lock_file = (
            f"/tmp/docker_build_{hashlib.md5(agent_image.encode()).hexdigest()}.lock"
        )
        try:
            with open(lock_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                yield f
        finally:
            Path(lock_file).unlink(missing_ok=True)

    def _create_temp_credential_file(self, content: str, suffix: str) -> str:
        """Create a secure temporary credential file that must be manually cleaned up"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=suffix) as f:
            f.write(content)
            f.flush()
            os.chmod(f.name, 0o600)
            return f.name

    def _cleanup_temp_files(self, temp_files: List[str]):
        """Clean up temporary credential files"""
        for temp_file in temp_files:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass

    def build_agent_image(self, base_image: str, cli_type: str = "claude") -> str:
        agent_image = (
            f"{cli_type}-agent-{hashlib.md5(base_image.encode()).hexdigest()[:10]}"
        ).lower()

        try:
            result = subprocess.run(
                ["docker", "images", "-q", agent_image],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.stdout.strip():
                print(f"🔄 Reusing existing image: {agent_image}")
                return agent_image
        except OSError as e:
            print(f"⚠️ Docker not available: {e}")
        except subprocess.SubprocessError as e:
            print(f"⚠️ Failed to check existing Docker image: {e}")

        print(f"🐳 Building agent image from {base_image}...")

        with self.docker_build_lock(agent_image):
            dockerfile_content = self.generate_agent_dockerfile(base_image, cli_type)

            with tempfile.TemporaryDirectory() as temp_dir:
                dockerfile_path = Path(temp_dir) / "Dockerfile"
                dockerfile_path.write_text(dockerfile_content)

                # Try current directory first, then fall back to package bundled version
                security_reqs_path = Path.cwd() / "security-requirements.txt"
                if not security_reqs_path.exists():
                    security_reqs_path = (
                        Path(__file__).parent / "security-requirements.txt"
                    )

                if security_reqs_path.exists():
                    subprocess.run(
                        [
                            "cp",
                            str(security_reqs_path),
                            str(Path(temp_dir) / "security-requirements.txt"),
                        ],
                        check=True,
                    )
                else:
                    # Fallback to default security tools
                    (Path(temp_dir) / "security-requirements.txt").write_text(
                        "bandit>=1.7.0\nsafety>=2.0.0\npip-audit>=2.0.0\n"
                    )

                # Copy refactored container directory
                container_dir = Path(__file__).parent / "container"
                if container_dir.exists():
                    subprocess.run(
                        ["cp", "-r", str(container_dir), str(temp_dir)],
                        check=True,
                    )
                else:
                    # Fallback to old entrypoint for backward compatibility
                    entrypoint_path = Path(__file__).parent / "container_entrypoint.sh"
                    if entrypoint_path.exists():
                        (Path(temp_dir) / "container").mkdir()
                        subprocess.run(
                            [
                                "cp",
                                str(entrypoint_path),
                                str(Path(temp_dir) / "container" / "entrypoint.sh"),
                            ],
                            check=True,
                        )

                # Copy github_utils.py for container operations
                github_utils_path = Path(__file__).parent / "github_utils.py"
                if github_utils_path.exists():
                    subprocess.run(
                        [
                            "cp",
                            str(github_utils_path),
                            str(Path(temp_dir) / "github_utils.py"),
                        ],
                        check=True,
                    )

                # Copy message_templates.py for container operations
                message_templates_path = Path(__file__).parent / "message_templates.py"
                if message_templates_path.exists():
                    subprocess.run(
                        [
                            "cp",
                            str(message_templates_path),
                            str(Path(temp_dir) / "message_templates.py"),
                        ],
                        check=True,
                    )

                try:
                    result = subprocess.run(
                        ["docker", "build", "-t", agent_image, temp_dir],
                        capture_output=True,
                        text=True,
                        timeout=self.DOCKER_BUILD_TIMEOUT,
                    )

                    if result.returncode != 0:
                        print(f"❌ Docker build failed: {result.stderr}")
                        raise RuntimeError(
                            f"Failed to build agent image: {result.stderr}"
                        )

                    print(f"✅ Built agent image: {agent_image}")
                    return agent_image

                except subprocess.TimeoutExpired:
                    print("❌ Docker build timed out after 5 minutes")
                    raise RuntimeError("Docker build timeout")

    def execute_in_container(
        self,
        agent_image: str,
        branch_name: str,
        task_spec: str,
        github_token: Optional[str] = None,
        ai_api_key: Optional[str] = None,
        job_id: Optional[str] = None,
        custom_envs: Optional[List[str]] = None,
        custom_volumes: Optional[List[str]] = None,
        cli_type: str = "claude",
        issue_number: Optional[str] = None,
    ) -> subprocess.Popen:
        container_name = f"{cli_type}-agent-{job_id}" if job_id else f"{cli_type}-agent"

        docker_cmd = [
            "docker",
            "run",
            "--name",
            container_name,
        ]

        # Track temp files for cleanup after container starts
        temp_files = []

        # Get GitHub token and username from gh CLI if not provided
        if not github_token:
            try:
                gh_token_result = subprocess.run(
                    ["gh", "auth", "status", "--show-token"], 
                    capture_output=True, text=True, check=False
                )
                if gh_token_result.returncode == 0:
                    # GitHub CLI outputs to stderr, check both stdout and stderr
                    output = gh_token_result.stdout + gh_token_result.stderr
                    if "Token:" in output:
                        # Extract token from "Token: gho_xxxx" line
                        for line in output.split('\n'):
                            if 'Token:' in line:
                                github_token = line.split('Token:')[1].strip()
                                print(f"✅ GitHub token configured ({len(github_token)} chars)")
                                break
            except Exception as e:
                print(f"⚠️  Warning: Could not get GitHub token: {e}")

        if github_token:
            docker_cmd.extend(["-e", f"GITHUB_TOKEN={github_token}"])

        # Get GitHub username for HTTPS authentication
        try:
            gh_user_result = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"], 
                capture_output=True, text=True, check=False
            )
            if gh_user_result.returncode == 0 and gh_user_result.stdout.strip():
                github_username = gh_user_result.stdout.strip()
                docker_cmd.extend(["-e", f"GITHUB_USERNAME={github_username}"])
                print(f"✅ GitHub username: {github_username}")
        except Exception as e:
            print(f"⚠️  Warning: Could not get GitHub username: {e}")

        # Pass Git configuration to container
        try:
            git_user_result = subprocess.run(
                ["git", "config", "--get", "user.name"], 
                capture_output=True, text=True, check=False
            )
            if git_user_result.returncode == 0 and git_user_result.stdout.strip():
                git_username = git_user_result.stdout.strip()
                # Escape quotes and special characters for Docker
                git_username_escaped = git_username.replace('"', '\\"')
                docker_cmd.extend(["-e", f"GIT_AUTHOR_NAME={git_username_escaped}"])
                docker_cmd.extend(["-e", f"GIT_COMMITTER_NAME={git_username_escaped}"])
                
            git_email_result = subprocess.run(
                ["git", "config", "--get", "user.email"], 
                capture_output=True, text=True, check=False
            )
            if git_email_result.returncode == 0 and git_email_result.stdout.strip():
                git_email = git_email_result.stdout.strip()
                git_email_escaped = git_email.replace('"', '\\"')
                docker_cmd.extend(["-e", f"GIT_AUTHOR_EMAIL={git_email_escaped}"])
                docker_cmd.extend(["-e", f"GIT_COMMITTER_EMAIL={git_email_escaped}"])
                
        except Exception as e:
            print(f"⚠️  Warning: Could not get Git user config: {e}")

        # Handle AI API key based on CLI type
        if ai_api_key:
            if cli_type == "claude":
                key_file = self._create_temp_credential_file(ai_api_key, ".key")
                temp_files.append(key_file)
                docker_cmd.extend(["-v", f"{key_file}:/tmp/anthropic_key:ro"])
            elif cli_type == "codex":
                docker_cmd.extend(["-e", f"OPENAI_API_KEY={ai_api_key}"])

        gitconfig_path = Path.home() / ".gitconfig"
        if gitconfig_path.exists() and self.validator:
            try:
                validated_path = self.validator.validate_mount_path(
                    gitconfig_path, "Git config"
                )
                docker_cmd.extend(["-v", f"{validated_path}:/root/.gitconfig:rw"])
            except ValueError as e:
                print(f"⚠️  Warning: Skipping git config: {e}")

        # Mount AI CLI config based on cli_type
        if cli_type == "claude":
            claude_json_path = Path.home() / ".claude.json"
            if claude_json_path.exists() and self.validator:
                try:
                    validated_path = self.validator.validate_mount_path(
                        claude_json_path, "Claude JSON config"
                    )
                    docker_cmd.extend(["-v", f"{validated_path}:/tmp/claude_credentials.json:ro"])
                except ValueError as e:
                    print(f"⚠️  Warning: Skipping Claude JSON config: {e}")
        elif cli_type == "gemini":
            gemini_config_path = Path.home() / ".config" / "gemini"
            if gemini_config_path.exists() and self.validator:
                try:
                    validated_path = self.validator.validate_mount_path(
                        gemini_config_path, "Gemini config"
                    )
                    docker_cmd.extend(
                        ["-v", f"{validated_path}:/root/.config/gemini:ro"]
                    )
                except ValueError as e:
                    print(f"⚠️  Warning: Skipping Gemini config: {e}")

        if custom_volumes:
            for volume in custom_volumes:
                if ":" not in volume:
                    print(f"⚠️  Warning: Invalid volume format: {volume}")
                    continue

                host_path, container_path = volume.split(":", 1)
                permissions = "rw"
                if ":" in container_path:
                    container_path, permissions = container_path.rsplit(":", 1)

                try:
                    host_path_obj = Path(host_path)
                    if self.validator:
                        validated_host_path = self.validator.validate_mount_path(
                            host_path_obj, f"Custom volume {host_path}"
                        )
                        docker_cmd.extend(
                            [
                                "-v",
                                f"{validated_host_path}:{container_path}:{permissions}",
                            ]
                        )
                    else:
                        docker_cmd.extend(
                            ["-v", f"{host_path}:{container_path}:{permissions}"]
                        )
                except ValueError as e:
                    print(f"⚠️  Warning: Skipping volume {host_path}: {e}")

        if custom_envs:
            for env in custom_envs:
                try:
                    if self.validator:
                        validated_env = self.validator.validate_env_var(env)
                        docker_cmd.extend(["-e", validated_env])
                    else:
                        # Basic validation fallback
                        if self._is_safe_env_var(env):
                            docker_cmd.extend(["-e", env])
                        else:
                            print("⚠️  Warning: Skipping unsafe environment variable")
                except ValueError as e:
                    print(f"⚠️  Warning: Skipping invalid environment variable: {e}")

        # Set environment variables for the container instead of command arguments
        docker_cmd.extend(["-e", f"BRANCH_NAME={branch_name}"])
        
        # Set GitHub issue number environment variables for notifications
        if issue_number:
            # Handle both direct issue numbers and GitHub URLs
            if "github.com" in issue_number and "/issues/" in issue_number:
                # Extract issue number from URL like https://github.com/user/repo/issues/123
                issue_num = issue_number.split("/")[-1]
                docker_cmd.extend(["-e", f"GITHUB_ISSUE_NUMBER={issue_num}"])
            elif "github.com" in issue_number and "/pull/" in issue_number:
                # Extract PR number from URL like https://github.com/user/repo/pull/123
                pr_num = issue_number.split("/")[-1]
                docker_cmd.extend(["-e", f"PR_NUMBER={pr_num}"])
            else:
                # Assume it's a direct issue/PR number
                issue_num = issue_number.replace("#", "")
                docker_cmd.extend(["-e", f"GITHUB_ISSUE_NUMBER={issue_num}"])
        
        # Create task spec file
        import tempfile
        task_spec_fd, task_spec_path = tempfile.mkstemp(suffix=".md", prefix="task_spec_")
        try:
            with os.fdopen(task_spec_fd, 'w') as f:
                f.write(task_spec)
            docker_cmd.extend(["-v", f"{task_spec_path}:/tmp/task_spec.md:ro"])
            temp_files.append(task_spec_path)
        except Exception as e:
            os.close(task_spec_fd)
            raise

        # Mount cost data directory to persist Claude usage data
        if job_id:
            cost_data_host_dir = Path.cwd() / ".ai_cost_data" / job_id
            cost_data_host_dir.mkdir(parents=True, exist_ok=True)
            docker_cmd.extend(["-v", f"{cost_data_host_dir}:/tmp/cost_data:rw"])

        # Validate and sanitize other inputs
        try:
            if self.validator:
                validated_image = self.validator.sanitize_docker_image(agent_image)
                docker_cmd.append(validated_image)
            else:
                # Basic fallback validation
                if (
                    self._is_safe_input(agent_image)
                    and self._is_safe_input(branch_name)
                    and len(task_spec) < 50000
                ):
                    docker_cmd.append(agent_image)
                else:
                    raise ValueError(
                        "Input validation failed - unsafe parameters detected"
                    )
        except ValueError as e:
            print(f"❌ Input validation failed: {e}")
            raise
        try:
            print(f"🚀 Starting container: {container_name}")
            # First test if the command is valid by running it with --help or dry run
            try:
                # Test docker command execution
                process = subprocess.Popen(
                    docker_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                # Check if process started and wait briefly for any immediate failures
                import time
                time.sleep(1.0)  # Give more time to start
                
                if process.poll() is not None:
                    # Process already terminated
                    stdout, stderr = process.communicate()
                    print(f"❌ Container exited immediately with code {process.returncode}")
                    print(f"❌ Stdout: {stdout}")
                    print(f"❌ Stderr: {stderr}")
                    # Clean up temp files if container start failed
                    if temp_files:
                        self._cleanup_temp_files(temp_files)
                    return None
                else:
                    print(f"✅ Container appears to be starting successfully")
                    
            except Exception as e:
                print(f"❌ Failed to execute docker command: {e}")
                # Clean up temp files if container start failed
                if temp_files:
                    self._cleanup_temp_files(temp_files)
                return None
            # Clean up temp credential files after container starts
            if temp_files:
                self._cleanup_temp_files(temp_files)
            return process
        except Exception as e:
            # Clean up temp files if container start failed
            if temp_files:
                self._cleanup_temp_files(temp_files)
            print(f"❌ Failed to start container: {e}")
            raise
