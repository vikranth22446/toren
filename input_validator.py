#!/usr/bin/env python3

import argparse
import re
from pathlib import Path
from typing import List


class InputValidator:
    def __init__(self):
        self.branch_name_pattern = re.compile(r"^[a-zA-Z0-9._/-]{1,100}$")
        self.docker_image_pattern = re.compile(r"^[a-z0-9._/-]+(?::[a-zA-Z0-9._-]+)?$")
        self.github_issue_pattern = re.compile(
            r"^https://github\.com/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+/issues/\d+$"
        )

    def sanitize_branch_name(self, branch_name: str) -> str:
        if not branch_name:
            raise ValueError("Branch name cannot be empty")

        branch_name = branch_name.strip()

        if not self.branch_name_pattern.match(branch_name):
            raise ValueError(
                f"Invalid branch name format: {branch_name}. Use only letters, numbers, dots, underscores, hyphens, and forward slashes."
            )

        if any(
            char in branch_name for char in ["..", "~", "^", ":", "[", "]", "?", "*"]
        ):
            raise ValueError(
                f"Branch name contains forbidden characters: {branch_name}"
            )

        if branch_name.startswith("-") or branch_name.endswith("-"):
            raise ValueError(
                f"Branch name cannot start or end with hyphen: {branch_name}"
            )

        return branch_name

    def sanitize_docker_image(self, image_name: str) -> str:
        if not image_name:
            raise ValueError("Docker image name cannot be empty")

        image_name = image_name.strip().lower()

        if not self.docker_image_pattern.match(image_name):
            raise ValueError(
                f"Invalid Docker image format: {image_name}. Use format: name:tag or registry/name:tag"
            )

        if any(
            char in image_name
            for char in [";", "&", "|", "`", "$", "(", ")", "<", ">", '"', "'"]
        ):
            raise ValueError(
                f"Docker image name contains forbidden characters: {image_name}"
            )

        if len(image_name) > 200:
            raise ValueError(
                f"Docker image name too long (max 200 chars): {image_name}"
            )

        return image_name

    def sanitize_github_issue_url(self, issue_url: str) -> str:
        if not issue_url:
            raise ValueError("GitHub issue URL cannot be empty")

        issue_url = issue_url.strip()

        if not self.github_issue_pattern.match(issue_url):
            raise ValueError(f"Invalid GitHub issue URL format: {issue_url}")

        if len(issue_url) > 500:
            raise ValueError(f"GitHub issue URL too long: {issue_url}")

        return issue_url

    def sanitize_pr_number(self, pr_number: str) -> str:
        if not pr_number:
            raise ValueError("PR number cannot be empty")

        pr_number = pr_number.strip()

        if pr_number.isdigit():
            if len(pr_number) > 10:
                raise ValueError("PR number too long")
            return pr_number

        github_pr_pattern = r"^https://github\.com/[\w\-_.]+/[\w\-_.]+/pull/\d+$"
        if re.match(github_pr_pattern, pr_number):
            number = pr_number.split("/")[-1]
            if len(number) > 10:
                raise ValueError("PR number too long")
            return number

        raise ValueError(f"Invalid GitHub PR number or URL format: {pr_number}")

    def validate_mount_path(self, path: Path, description: str) -> Path:
        try:
            resolved_path = path.resolve()

            if not resolved_path.exists():
                raise ValueError(f"{description} does not exist: {resolved_path}")

            safe_dirs = [Path.home(), Path.cwd(), Path("/tmp"), Path("/var/tmp")]

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
                raise ValueError(
                    f"{description} is outside safe directories: {resolved_path}"
                )

            return resolved_path

        except OSError as e:
            raise ValueError(f"Invalid {description} - file system error: {e}")
        except PermissionError as e:
            raise ValueError(f"Invalid {description} - permission denied: {e}")
        except (TypeError, AttributeError) as e:
            raise ValueError(f"Invalid {description} - invalid path format: {e}")

    def validate_inputs(self, args: argparse.Namespace) -> bool:
        try:
            input_count = sum(bool(x) for x in [args.spec, args.issue, args.pr])
            if input_count == 0:
                print("❌ Error: Must provide one of --spec, --issue, or --pr")
                return False
            elif input_count > 1:
                print(
                    "❌ Error: Can only specify one of --spec, --issue, or --pr at a time"
                )
                return False

            if args.spec and not Path(args.spec).exists():
                print(f"❌ Error: Spec file not found: {args.spec}")
                return False

            if args.issue:
                try:
                    args.issue = self.sanitize_github_issue_url(args.issue)
                except ValueError as e:
                    print(f"❌ Error: {e}")
                    return False

            if args.pr:
                try:
                    args.pr = self.sanitize_pr_number(args.pr)
                except ValueError as e:
                    print(f"❌ Error: {e}")
                    return False

            if not args.pr and not args.branch:
                print("❌ Error: --branch is required when not using --pr mode")
                return False
            elif args.branch:
                try:
                    args.branch = self.sanitize_branch_name(args.branch)
                except ValueError as e:
                    print(f"❌ Error: {e}")
                    return False

            if not args.base_image:
                print(
                    "❌ Error: --base-image is required. Set it via command line or config.json"
                )
                return False

            try:
                args.base_image = self.sanitize_docker_image(args.base_image)
            except ValueError as e:
                print(f"❌ Error: {e}")
                return False

            return True

        except (AttributeError, TypeError) as e:
            print(f"❌ Input validation error - invalid argument format: {e}")
            return False
        except ValueError as e:
            print(f"❌ Input validation error - invalid value: {e}")
            return False
        except RuntimeError as e:
            print(f"❌ Input validation error - runtime issue: {e}")
            return False

    def validate_spec_safety(self, content: str) -> List[str]:
        concerns = []

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

        if len(content.split("\n")) > 100:
            concerns.append("Spec is very large - may result in oversized PR")

        return concerns

    def validate_env_var(self, env_var: str) -> str:
        """Validate environment variable is safe for Docker execution"""
        if not env_var:
            raise ValueError("Environment variable cannot be empty")

        if "=" not in env_var:
            raise ValueError("Environment variable must be in KEY=VALUE format")

        key, value = env_var.split("=", 1)

        # Validate key (environment variable name)
        if not key:
            raise ValueError("Environment variable name cannot be empty")

        if not re.match(r"^[A-Z_][A-Z0-9_]*$", key):
            raise ValueError(
                f"Invalid environment variable name: {key}. "
                "Must start with letter/underscore and contain only uppercase letters, numbers, underscores."
            )

        # Validate value - no dangerous characters
        dangerous_chars = [";", "`", "$", "(", ")", "\n", "\r", "\\", "|", "&"]
        found_dangerous = [char for char in dangerous_chars if char in value]
        if found_dangerous:
            raise ValueError(
                f"Environment variable value contains dangerous characters: {', '.join(found_dangerous)}"
            )

        # Length limits to prevent DoS
        if len(key) > 100:
            raise ValueError(
                f"Environment variable name too long: {len(key)} chars (max: 100)"
            )

        if len(value) > 1000:
            raise ValueError(
                f"Environment variable value too long: {len(value)} chars (max: 1000)"
            )

        # No control characters
        if any(ord(char) < 32 and char not in ["\t"] for char in value):
            raise ValueError("Environment variable value contains control characters")

        return env_var

    def validate_task_spec(self, task_spec: str) -> str:
        """Validate task specification content"""
        if not task_spec:
            raise ValueError("Task specification cannot be empty")

        if len(task_spec) > 50000:  # 50KB limit
            raise ValueError(
                f"Task specification too large: {len(task_spec)} chars (max: 50000)"
            )

        # Check for binary/non-text content
        try:
            task_spec.encode("utf-8")
        except UnicodeError:
            raise ValueError("Task specification contains invalid characters")

        return task_spec
