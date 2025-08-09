#!/usr/bin/env python3

import os
import json
import re
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path


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
            }
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
            print(f"\n📋 **Cost Factors:**")
            for factor in estimate["cost_factors"]:
                print(f"  • {factor}")

        if "cost_reduction_tips" in estimate and estimate["cost_reduction_tips"]:
            print(f"\n💡 **Cost Reduction Tips:**")
            for tip in estimate["cost_reduction_tips"]:
                print(f"  • {tip}")

        if "raw_response" in estimate:
            print(f"\n🔍 **Raw Response Preview:**")
            print(
                estimate["raw_response"][:300] + "..."
                if len(estimate["raw_response"]) > 300
                else estimate["raw_response"]
            )

        print()
