#!/usr/bin/env python3

import fcntl
import hashlib
import os
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
COPY container/ /usr/local/
COPY github_utils.py /usr/local/bin/github_utils.py
COPY message_templates.py /usr/local/bin/message_templates.py
RUN chmod +x /usr/local/entrypoint.sh /usr/local/lib/*.sh /usr/local/lib/*.py /usr/local/bin/github_utils.py

WORKDIR /workspace
ENTRYPOINT ["/usr/local/entrypoint.sh"]
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
        )

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
        anthropic_api_key: Optional[str] = None,
        job_id: Optional[str] = None,
        custom_envs: Optional[List[str]] = None,
        custom_volumes: Optional[List[str]] = None,
        cli_type: str = "claude",
    ) -> subprocess.Popen:
        container_name = f"{cli_type}-agent-{job_id}" if job_id else f"{cli_type}-agent"

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
        ]

        # Track temp files for cleanup after container starts
        temp_files = []

        if github_token:
            token_file = self._create_temp_credential_file(github_token, ".token")
            temp_files.append(token_file)
            docker_cmd.extend(["-v", f"{token_file}:/tmp/github_token:ro"])

        if anthropic_api_key:
            key_file = self._create_temp_credential_file(anthropic_api_key, ".key")
            temp_files.append(key_file)
            docker_cmd.extend(["-v", f"{key_file}:/tmp/anthropic_key:ro"])

        gitconfig_path = Path.home() / ".gitconfig"
        if gitconfig_path.exists() and self.validator:
            try:
                validated_path = self.validator.validate_mount_path(
                    gitconfig_path, "Git config"
                )
                docker_cmd.extend(["-v", f"{validated_path}:/root/.gitconfig:ro"])
            except ValueError as e:
                print(f"⚠️  Warning: Skipping git config: {e}")

        ssh_path = Path.home() / ".ssh"
        if ssh_path.exists() and self.validator:
            try:
                validated_path = self.validator.validate_mount_path(
                    ssh_path, "SSH directory"
                )
                docker_cmd.extend(["-v", f"{validated_path}:/root/.ssh:ro"])
            except ValueError as e:
                print(f"⚠️  Warning: Skipping SSH keys: {e}")

        # Mount AI CLI config based on cli_type
        if cli_type == "claude":
            claude_json_path = Path.home() / ".claude.json"
            if claude_json_path.exists() and self.validator:
                try:
                    validated_path = self.validator.validate_mount_path(
                        claude_json_path, "Claude JSON config"
                    )
                    docker_cmd.extend(["-v", f"{validated_path}:/root/.claude.json:ro"])
                except ValueError as e:
                    print(f"⚠️  Warning: Skipping Claude JSON config: {e}")

            claude_dir_path = Path.home() / ".claude"
            if claude_dir_path.exists() and self.validator:
                try:
                    validated_path = self.validator.validate_mount_path(
                        claude_dir_path, "Claude Code config"
                    )
                    docker_cmd.extend(["-v", f"{validated_path}:/root/.claude:ro"])
                except ValueError as e:
                    print(f"⚠️  Warning: Skipping Claude directory: {e}")
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

        docker_cmd.extend(["-v", f"{Path.cwd()}:/workspace"])

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

        # Validate and sanitize other inputs
        try:
            if self.validator:
                validated_image = self.validator.sanitize_docker_image(agent_image)
                validated_branch = self.validator.sanitize_branch_name(branch_name)
                validated_task_spec = self.validator.validate_task_spec(task_spec)
                docker_cmd.extend(
                    [validated_image, validated_branch, validated_task_spec]
                )
            else:
                # Basic fallback validation
                if (
                    self._is_safe_input(agent_image)
                    and self._is_safe_input(branch_name)
                    and len(task_spec) < 50000
                ):
                    docker_cmd.extend([agent_image, branch_name, task_spec])
                else:
                    raise ValueError(
                        "Input validation failed - unsafe parameters detected"
                    )
        except ValueError as e:
            print(f"❌ Input validation failed: {e}")
            raise

        try:
            print(f"🚀 Starting container: {container_name}")
            process = subprocess.Popen(
                docker_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
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
