#!/usr/bin/env python3
"""
Claude Cost Tracker - Extract cost and usage information from Claude Code execution
"""

import json
import re
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class ClaudeCostTracker:
    def __init__(self):
        self.cost_file = Path("/tmp/claude_session_cost.json")
        self.output_file = Path("/tmp/claude_output.log")
        
    def initialize_cost_tracking(self) -> None:
        """Initialize cost tracking file"""
        initial_data = {
            "session_start": datetime.now(timezone.utc).isoformat(),
            "total_cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "model": "claude-3-5-sonnet",
            "executions": [],
            "lines_changed": {
                "added": 0,
                "deleted": 0,
                "total": 0
            },
            "git_stats": {
                "files_changed": 0,
                "commits_made": 0
            }
        }
        
        with open(self.cost_file, 'w') as f:
            json.dump(initial_data, f, indent=2)
            
    def execute_claude_with_tracking(self, prompt: str) -> int:
        """Execute Claude Code and capture cost information"""
        print("🤖 Executing Claude Code with cost tracking...")
        
        # Execute Claude and capture all output
        try:
            with open(self.output_file, 'w') as output_file:
                process = subprocess.Popen([
                    "claude", "--dangerously-skip-permissions", "--print", prompt
                ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                   universal_newlines=True, bufsize=1)
                
                # Stream output in real-time while capturing it
                for line in process.stdout:
                    print(line, end='')  # Print to console
                    output_file.write(line)  # Save to file
                    output_file.flush()
                
                process.wait()
                return process.returncode
                
        except Exception as e:
            print(f"❌ Error executing Claude Code: {e}")
            return 1
            
    def parse_cost_from_output(self) -> Dict[str, Any]:
        """Parse cost and token information from Claude Code output"""
        cost_info = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "cost_found": False,
            "raw_cost_lines": []
        }
        
        if not self.output_file.exists():
            return cost_info
            
        try:
            with open(self.output_file, 'r') as f:
                output_text = f.read()
                
            # Look for cost-related information
            cost_patterns = [
                r'cost[:\s]*\$?([\d.]+)',
                r'total[:\s]*\$?([\d.]+)',
                r'input[:\s]*(\d+)[:\s]*token',
                r'output[:\s]*(\d+)[:\s]*token',
                r'(\d+)[:\s]*input[:\s]*token',
                r'(\d+)[:\s]*output[:\s]*token',
            ]
            
            cost_lines = []
            for line in output_text.split('\n'):
                if any(keyword in line.lower() for keyword in ['cost', 'token', 'usage', 'price']):
                    cost_lines.append(line.strip())
                    
            cost_info["raw_cost_lines"] = cost_lines
            
            if cost_lines:
                cost_info["cost_found"] = True
                print("💰 Found cost information:")
                for line in cost_lines:
                    print(f"  {line}")
                    
                # Try to extract specific values
                for line in cost_lines:
                    # Look for dollar amounts
                    dollar_match = re.search(r'\$?([\d.]+)', line.lower())
                    if dollar_match and 'cost' in line.lower():
                        cost_info["total_cost"] = float(dollar_match.group(1))
                        
                    # Look for token counts
                    if 'input' in line.lower():
                        token_match = re.search(r'(\d+)', line)
                        if token_match:
                            cost_info["input_tokens"] = int(token_match.group(1))
                            
                    if 'output' in line.lower():
                        token_match = re.search(r'(\d+)', line)
                        if token_match:
                            cost_info["output_tokens"] = int(token_match.group(1))
            else:
                print("ℹ️  No explicit cost information found in output")
                
        except Exception as e:
            print(f"⚠️  Error parsing cost information: {e}")
            
        return cost_info
        
    def calculate_lines_changed(self) -> Dict[str, int]:
        """Calculate lines changed using git diff"""
        print("📏 Calculating lines changed...")
        
        lines_info = {
            "added": 0,
            "deleted": 0,
            "total": 0,
            "files_changed": 0
        }
        
        try:
            # Check if there are any changes
            status_result = subprocess.run([
                "git", "status", "--porcelain"
            ], capture_output=True, text=True)
            
            if not status_result.stdout.strip():
                print("ℹ️  No changes detected")
                return lines_info
                
            # Get diff statistics
            diff_result = subprocess.run([
                "git", "diff", "--stat", "HEAD"
            ], capture_output=True, text=True)
            
            if diff_result.returncode == 0 and diff_result.stdout:
                diff_output = diff_result.stdout.strip()
                
                # Parse the summary line (usually the last line)
                lines = diff_output.split('\n')
                if lines:
                    summary_line = lines[-1]
                    
                    # Extract insertions
                    insertion_match = re.search(r'(\d+) insertion', summary_line)
                    if insertion_match:
                        lines_info["added"] = int(insertion_match.group(1))
                        
                    # Extract deletions  
                    deletion_match = re.search(r'(\d+) deletion', summary_line)
                    if deletion_match:
                        lines_info["deleted"] = int(deletion_match.group(1))
                        
                    # Count files changed
                    files_match = re.search(r'(\d+) file', summary_line)
                    if files_match:
                        lines_info["files_changed"] = int(files_match.group(1))
                        
                lines_info["total"] = lines_info["added"] + lines_info["deleted"]
                
                print(f"📊 Lines changed: +{lines_info['added']} -{lines_info['deleted']} " +
                      f"(total: {lines_info['total']}) across {lines_info['files_changed']} files")
            else:
                print("ℹ️  Unable to get diff statistics")
                
        except Exception as e:
            print(f"⚠️  Error calculating lines changed: {e}")
            
        return lines_info
        
    def update_cost_tracking(self, cost_info: Dict[str, Any], lines_info: Dict[str, int]) -> None:
        """Update the cost tracking file with execution data"""
        try:
            # Load existing data
            if self.cost_file.exists():
                with open(self.cost_file, 'r') as f:
                    data = json.load(f)
            else:
                self.initialize_cost_tracking()
                with open(self.cost_file, 'r') as f:
                    data = json.load(f)
                    
            # Update with new execution data
            execution_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cost": cost_info["total_cost"],
                "input_tokens": cost_info["input_tokens"],
                "output_tokens": cost_info["output_tokens"],
                "cost_found": cost_info["cost_found"],
                "raw_cost_info": cost_info["raw_cost_lines"]
            }
            
            data["executions"].append(execution_data)
            
            # Update totals
            data["total_cost"] += cost_info["total_cost"]
            data["input_tokens"] += cost_info["input_tokens"] 
            data["output_tokens"] += cost_info["output_tokens"]
            
            # Update lines changed
            data["lines_changed"] = lines_info
            
            # Save updated data
            with open(self.cost_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            print(f"💾 Updated cost tracking: ${data['total_cost']:.4f} total")
            
        except Exception as e:
            print(f"❌ Error updating cost tracking: {e}")
            
    def get_session_summary(self) -> Optional[Dict[str, Any]]:
        """Get current session cost summary"""
        if not self.cost_file.exists():
            return None
            
        try:
            with open(self.cost_file, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"❌ Error reading cost tracking: {e}")
            return None
            
    def print_session_summary(self) -> None:
        """Print a formatted session summary"""
        summary = self.get_session_summary()
        if not summary:
            print("ℹ️  No cost tracking data available")
            return
            
        print("📈 Session Summary:")
        print(f"  💰 Total Cost: ${summary['total_cost']:.4f}")
        print(f"  🔤 Tokens: {summary['input_tokens']} input + {summary['output_tokens']} output")
        print(f"  📝 Lines: +{summary['lines_changed']['added']} -{summary['lines_changed']['deleted']} " +
              f"(total: {summary['lines_changed']['total']})")
        print(f"  📁 Files changed: {summary['lines_changed']['files_changed']}")
        print(f"  ⚡ Executions: {len(summary['executions'])}")


def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: claude_cost_tracker.py <command> [args...]")
        print("Commands:")
        print("  init                    - Initialize cost tracking")
        print("  execute <prompt>        - Execute Claude Code with cost tracking")  
        print("  summary                 - Show session summary")
        print("  get-json                - Output cost data as JSON")
        sys.exit(1)
        
    tracker = ClaudeCostTracker()
    command = sys.argv[1]
    
    if command == "init":
        tracker.initialize_cost_tracking()
        print("✅ Cost tracking initialized")
        
    elif command == "execute":
        if len(sys.argv) < 3:
            print("Error: execute command requires a prompt")
            sys.exit(1)
            
        prompt = sys.argv[2]
        
        # Initialize if needed
        if not tracker.cost_file.exists():
            tracker.initialize_cost_tracking()
            
        # Execute Claude Code
        exit_code = tracker.execute_claude_with_tracking(prompt)
        
        # Parse cost information
        cost_info = tracker.parse_cost_from_output()
        lines_info = tracker.calculate_lines_changed()
        
        # Update tracking
        tracker.update_cost_tracking(cost_info, lines_info)
        
        # Print summary
        tracker.print_session_summary()
        
        sys.exit(exit_code)
        
    elif command == "summary":
        tracker.print_session_summary()
        
    elif command == "get-json":
        summary = tracker.get_session_summary()
        if summary:
            print(json.dumps(summary, indent=2))
        else:
            print("{}")
            
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()