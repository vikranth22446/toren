#!/usr/bin/env python3

import json
import os
import re
import subprocess
from typing import Any, Dict, Optional


class AICliInterface:
    # Timeout constants (in seconds)
    CLI_COMMAND_TIMEOUT = 30  # For Claude CLI API calls

    def __init__(self, cli_type: str = "claude"):
        self.cli_type = cli_type
        self.cli_configs = {
            "claude": {
                "command": "claude",
                "api_key_env": "ANTHROPIC_API_KEY",
                "model": "claude-3-5-sonnet",
                "print_flag": "--print",
            },
            "gemini": {
                "command": "gemini",
                "api_key_env": "GEMINI_API_KEY",
                "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                "print_flag": "-p",
            },
            "codex": {
                "command": "codex",
                "api_key_env": "OPENAI_API_KEY",
                "model": "gpt-5",
                "print_flag": "exec",
            },
        }
        self.config = self.cli_configs.get(cli_type, self.cli_configs["claude"])

    def get_api_key(self) -> Optional[str]:
        api_key_env = self.config["api_key_env"]
        if api_key_env in os.environ and os.environ[api_key_env].strip():
            return os.environ[api_key_env]
        return None

    def get_language_config(self, language: str) -> Dict[str, str]:
        configs = {
            "python": {
                "security_tools": "bandit safety pip-audit",
                "test_command": "python -m pytest",
                "lint_command": "python -m flake8",
                "build_command": "python -m pip install -e .",
                "security_scan": "bandit -r . && safety check && pip-audit",
            },
            "rust": {
                "security_tools": "cargo-audit cargo-deny",
                "test_command": "cargo test",
                "lint_command": "cargo clippy -- -D warnings",
                "build_command": "cargo build",
                "security_scan": "cargo audit && cargo clippy && cargo deny check",
            },
        }
        return configs.get(language, configs["python"])

    def estimate_task_cost(
        self, task_content: str, language: str = "python"
    ) -> Optional[Dict[str, Any]]:
        try:
            print("💰 Asking Claude to estimate task cost...")

            estimation_prompt = f"""Analyze this task specification and estimate the \
Claude API cost to complete it:

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

            result = subprocess.run(
                [self.config["command"], self.config["print_flag"], estimation_prompt],
                capture_output=True,
                text=True,
                timeout=self.CLI_COMMAND_TIMEOUT,
            )

            if result.returncode == 0:
                output = result.stdout.strip()

                json_match = re.search(r"\{[^}]+\}", output, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    estimate_data = json.loads(json_str)

                    estimate_data["language"] = language
                    estimate_data["model"] = self.config["model"]
                    estimate_data["raw_response"] = output

                    return estimate_data
                else:
                    return {
                        "complexity": "unknown",
                        "estimated_total_cost": 0.02,
                        "raw_response": output,
                        "language": language,
                        "model": self.config["model"],
                        "confidence": "low",
                    }
            else:
                print(f"⚠️  Warning: Cost estimation failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print("⚠️  Warning: Cost estimation timed out")
            return None
        except Exception as e:
            print(f"⚠️  Warning: Could not estimate cost: {e}")
            return None

    def print_cost_estimate(
        self, estimate: Dict[str, Any], task_type: str = "task"
    ) -> None:
        if not estimate:
            print("❌ Cost estimation unavailable")
            return

        print(f"\n💰 **{self.cli_type.title()}'s Cost Estimate for {task_type}**")
        print("-" * 50)

        if "complexity" in estimate:
            complexity_emoji = {"simple": "🟢", "medium": "🟡", "complex": "🔴"}.get(
                estimate["complexity"], "⚪"
            )
            print(f"{complexity_emoji} Complexity: {estimate['complexity'].title()}")

        if "estimated_input_tokens" in estimate:
            print(f"🔤 Est. Input Tokens: {estimate['estimated_input_tokens']:,}")
        if "estimated_output_tokens" in estimate:
            print(f"📝 Est. Output Tokens: {estimate['estimated_output_tokens']:,}")

        if "estimated_total_cost" in estimate:
            print(f"💰 **Estimated Cost: ${estimate['estimated_total_cost']:.4f}**")

        if "confidence" in estimate:
            conf_emoji = {"high": "🎯", "medium": "📊", "low": "🤔"}.get(
                estimate["confidence"], "❓"
            )
            print(f"{conf_emoji} Confidence: {estimate['confidence'].title()}")

        print(f"🤖 Model: {estimate.get('model', self.config['model'])}")
        print(f"🔧 Language: {estimate.get('language', 'unknown')}")

        if "cost_factors" in estimate and estimate["cost_factors"]:
            print("\n📋 **Cost Factors:**")
            for factor in estimate["cost_factors"]:
                print(f"  • {factor}")

        if "cost_reduction_tips" in estimate and estimate["cost_reduction_tips"]:
            print("\n💡 **Cost Reduction Tips:**")
            for tip in estimate["cost_reduction_tips"]:
                print(f"  • {tip}")

        if "raw_response" in estimate:
            print("\n🔍 **Raw Response Preview:**")
            print(
                estimate["raw_response"][:300] + "..."
                if len(estimate["raw_response"]) > 300
                else estimate["raw_response"]
            )

        print()

    def check_short_description_quality(self, short_description: str) -> Dict[str, Any]:
        """
        Check if a short description is clear and actionable enough for task execution.
        Returns quality assessment with clarity score and recommendations.
        """
        try:
            print("🔍 Checking description quality...")

            quality_prompt = f"""Analyze this short task description for clarity and actionability:

TASK DESCRIPTION:
{short_description}

Please assess if this description is clear enough for an AI agent to \
understand and execute the task. Consider:

1. Is the goal/objective clear?
2. Are the requirements specific enough?
3. Is the scope well-defined?
4. Are there enough actionable details?
5. Are there any ambiguities that could lead to wrong implementation?

Respond with a JSON object in this format:
{{
    "is_clear": true/false,
    "clarity_score": 1-10,
    "issues": ["list of specific issues if any"],
    "recommendations": ["suggestions to improve clarity"],
    "assessment": "brief overall assessment"
}}

Be strict - only mark as clear (true) if the description provides \
enough detail for confident implementation."""

            result = subprocess.run(
                [self.config["command"], self.config["print_flag"], quality_prompt],
                capture_output=True,
                text=True,
                timeout=self.CLI_COMMAND_TIMEOUT,
            )

            if result.returncode == 0:
                output = result.stdout.strip()

                json_match = re.search(r"\{[^}]+\}", output, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    quality_data = json.loads(json_str)
                    quality_data["raw_response"] = output
                    return quality_data
                else:
                    # Fallback if JSON parsing fails
                    return {
                        "is_clear": False,
                        "clarity_score": 3,
                        "issues": ["Could not parse quality assessment"],
                        "recommendations": ["Try providing more specific details"],
                        "assessment": "Assessment failed - assuming unclear",
                        "raw_response": output,
                    }
            else:
                print(f"⚠️  Warning: Quality check failed: {result.stderr}")
                return {
                    "is_clear": False,
                    "clarity_score": 3,
                    "issues": ["Quality check service unavailable"],
                    "recommendations": ["Provide more detailed specification"],
                    "assessment": "Could not assess quality",
                }

        except subprocess.TimeoutExpired:
            print("⚠️  Warning: Quality check timed out")
            return {
                "is_clear": False,
                "clarity_score": 3,
                "issues": ["Quality check timed out"],
                "recommendations": ["Try with a more detailed specification"],
                "assessment": "Assessment timeout",
            }
        except Exception as e:
            print(f"⚠️  Warning: Quality check error: {e}")
            return {
                "is_clear": False,
                "clarity_score": 3,
                "issues": [f"Error during assessment: {str(e)}"],
                "recommendations": ["Provide more detailed specification"],
                "assessment": "Assessment error",
            }

    def print_quality_assessment(self, quality: Dict[str, Any]) -> None:
        """Print formatted quality assessment results"""
        print("\n🔍 **Task Description Quality Assessment**")
        print("-" * 50)

        if "clarity_score" in quality:
            score = quality["clarity_score"]
            if score >= 8:
                score_emoji = "🟢"
                score_desc = "Excellent"
            elif score >= 6:
                score_emoji = "🟡"
                score_desc = "Good"
            elif score >= 4:
                score_emoji = "🟠"
                score_desc = "Fair"
            else:
                score_emoji = "🔴"
                score_desc = "Poor"

            print(f"{score_emoji} Clarity Score: {score}/10 ({score_desc})")

        if "is_clear" in quality:
            clear_emoji = "✅" if quality["is_clear"] else "❌"
            clear_status = "Clear" if quality["is_clear"] else "Unclear"
            print(f"{clear_emoji} Overall Assessment: {clear_status}")

        if "assessment" in quality:
            print(f"📝 Summary: {quality['assessment']}")

        if "issues" in quality and quality["issues"]:
            print("\n⚠️  **Issues Found:**")
            for issue in quality["issues"]:
                print(f"  • {issue}")

        if "recommendations" in quality and quality["recommendations"]:
            print("\n💡 **Recommendations:**")
            for rec in quality["recommendations"]:
                print(f"  • {rec}")

        print()

    def generate_dockerfile(
        self, project_path: str, base_image: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a Dockerfile by analyzing the current codebase using AI.
        Returns the generated Dockerfile content or None on failure.
        """
        try:
            print("🐳 Generating Dockerfile using AI analysis...")
            
            # Analyze project structure
            project_files = []
            try:
                for root, dirs, files in os.walk(project_path):
                    # Skip hidden directories and common build/cache directories
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'target', 'build', 'dist']]
                    
                    for file in files:
                        if not file.startswith('.') and file.endswith(('.py', '.js', '.ts', '.go', '.rs', '.java', '.rb', '.php', '.txt', '.json', '.yaml', '.yml', '.toml', '.lock')):
                            rel_path = os.path.relpath(os.path.join(root, file), project_path)
                            project_files.append(rel_path)
                
                # Limit to first 30 files to avoid token limits
                project_files = project_files[:30]
            except Exception as e:
                print(f"⚠️  Warning: Could not analyze project structure: {e}")
                project_files = []

            # Create prompt for Dockerfile generation
            base_image_instruction = f"Use '{base_image}' as the base image." if base_image else "Select an appropriate base image based on the project type."
            
            dockerfile_prompt = f"""Analyze this project structure and generate an optimized Dockerfile:

PROJECT FILES:
{chr(10).join(project_files) if project_files else "No files found - generate a basic Dockerfile"}

REQUIREMENTS:
1. {base_image_instruction}
2. Detect the primary language/framework from the files
3. Install necessary system dependencies
4. Copy application files efficiently
5. Set appropriate working directory
6. Install application dependencies (requirements.txt, package.json, Cargo.toml, etc.)
7. Expose relevant ports if it's a web application
8. Set proper entrypoint/command
9. Follow Docker best practices (layer caching, minimize layers, non-root user if applicable)
10. Add health checks if appropriate

Generate a production-ready Dockerfile with comments explaining each section.
Respond with ONLY the Dockerfile content - no additional text or explanations."""

            result = subprocess.run(
                [self.config["command"], self.config["print_flag"], dockerfile_prompt],
                capture_output=True,
                text=True,
                timeout=self.CLI_COMMAND_TIMEOUT,
            )

            if result.returncode == 0:
                dockerfile_content = result.stdout.strip()
                
                # Clean up the response - remove any markdown code blocks or extra text
                if dockerfile_content.startswith("```"):
                    lines = dockerfile_content.split('\n')
                    start_idx = 1 if lines[0].startswith("```") else 0
                    end_idx = len(lines)
                    for i in range(len(lines)-1, -1, -1):
                        if lines[i].strip() == "```":
                            end_idx = i
                            break
                    dockerfile_content = '\n'.join(lines[start_idx:end_idx])
                
                return dockerfile_content.strip()
            else:
                print(f"❌ Dockerfile generation failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print("❌ Dockerfile generation timed out")
            return None
        except Exception as e:
            print(f"❌ Error generating Dockerfile: {e}")
            return None
