#!/usr/bin/env python3
"""
Cost monitoring and session tracking module
"""

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class CostMonitor:
    def __init__(self):
        self.cost_file = Path("/tmp/claude_cost_data.json")
        self.output_file = Path("/tmp/claude_cost_monitor.json")

    def initialize_tracking(self):
        """Initialize cost tracking data"""
        initial_data = {
            "total_cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "session_start": datetime.now(timezone.utc).isoformat(),
        }

        with open(self.cost_file, "w") as f:
            json.dump(initial_data, f)

    def update_costs(
        self,
        input_tokens: int,
        output_tokens: int,
        input_price: float = 0.000003,
        output_price: float = 0.000015,
    ):
        """Update cost tracking with new token usage"""
        try:
            if self.cost_file.exists():
                with open(self.cost_file, "r") as f:
                    data = json.load(f)
            else:
                data = {"total_cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        except Exception:
            data = {"total_cost": 0.0, "input_tokens": 0, "output_tokens": 0}

        # Update counts
        data["input_tokens"] += input_tokens
        data["output_tokens"] += output_tokens
        data["total_cost"] += (input_tokens * input_price) + (
            output_tokens * output_price
        )

        # Save updated data
        try:
            with open(self.cost_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def get_git_stats(self, starting_commit: Optional[str] = None) -> Dict[str, int]:
        """Get git statistics for the session"""
        git_stats = {
            "files_changed": 0,
            "lines_added": 0,
            "lines_deleted": 0,
            "total_lines_changed": 0,
        }

        if not starting_commit:
            return git_stats

        try:
            # Get diff stats
            result = subprocess.run(
                ["git", "diff", "--stat", f"{starting_commit}..HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0 and result.stdout.strip():
                summary_line = result.stdout.strip().split("\n")[-1]

                # Parse stats
                insertion_match = re.search(r"(\d+) insertion", summary_line)
                if insertion_match:
                    git_stats["lines_added"] = int(insertion_match.group(1))

                deletion_match = re.search(r"(\d+) deletion", summary_line)
                if deletion_match:
                    git_stats["lines_deleted"] = int(deletion_match.group(1))

                files_match = re.search(r"(\d+) file", summary_line)
                if files_match:
                    git_stats["files_changed"] = int(files_match.group(1))

                git_stats["total_lines_changed"] = (
                    git_stats["lines_added"] + git_stats["lines_deleted"]
                )

        except Exception:
            pass

        return git_stats

    def finalize_session(self, starting_commit: Optional[str] = None) -> Dict[str, Any]:
        """Generate final session summary"""

        # Load cost data
        try:
            if self.cost_file.exists():
                with open(self.cost_file, "r") as f:
                    cost_data = json.load(f)
            else:
                cost_data = {"total_cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        except Exception:
            cost_data = {"total_cost": 0.0, "input_tokens": 0, "output_tokens": 0}

        # Get git stats
        git_stats = self.get_git_stats(starting_commit)

        # Create session summary
        session_data = {
            "session_start": cost_data.get(
                "session_start", datetime.now(timezone.utc).isoformat()
            ),
            "session_end": datetime.now(timezone.utc).isoformat(),
            "cost": cost_data,
            "git_stats": git_stats,
            "summary": {
                "total_cost": cost_data["total_cost"],
                "total_tokens": cost_data["input_tokens"] + cost_data["output_tokens"],
                "input_tokens": cost_data["input_tokens"],
                "output_tokens": cost_data["output_tokens"],
                "lines_changed": git_stats["total_lines_changed"],
                "files_changed": git_stats["files_changed"],
            },
        }

        # Print summary
        print("📈 Session Summary:")
        print(f"  💰 Cost: ${session_data['summary']['total_cost']:.4f}")
        print(f"  🔤 Tokens: {session_data['summary']['total_tokens']:,}")
        print(f"  📝 Lines changed: {session_data['summary']['lines_changed']}")
        print(f"  📁 Files modified: {session_data['summary']['files_changed']}")

        # Save session data
        with open(self.output_file, "w") as f:
            json.dump(session_data, f, indent=2)

        # Export for job manager
        cost_dir = Path("/tmp/cost_data")
        if cost_dir.exists():
            import shutil

            shutil.copy(self.output_file, cost_dir / "session_cost.json")
            print("💾 Cost data exported for job manager")

        return session_data


def main():
    parser = argparse.ArgumentParser(description="Cost Monitor")
    parser.add_argument(
        "--initialize", action="store_true", help="Initialize cost tracking"
    )
    parser.add_argument(
        "--finalize", action="store_true", help="Finalize session and generate summary"
    )
    parser.add_argument("--starting-commit", help="Starting commit hash for git stats")
    parser.add_argument(
        "--update", action="store_true", help="Update costs with token usage"
    )
    parser.add_argument("--input-tokens", type=int, default=0, help="Input tokens used")
    parser.add_argument(
        "--output-tokens", type=int, default=0, help="Output tokens used"
    )

    args = parser.parse_args()

    monitor = CostMonitor()

    if args.initialize:
        monitor.initialize_tracking()
    elif args.finalize:
        monitor.finalize_session(args.starting_commit)
    elif args.update:
        monitor.update_costs(args.input_tokens, args.output_tokens)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
