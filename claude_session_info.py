#!/usr/bin/env python3
"""
Claude Session Info - Get cost and usage data from Claude Code's built-in commands
"""

import json
import subprocess
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


class ClaudeSessionInfo:
    def __init__(self):
        self.session_file = Path("/tmp/claude_session_info.json")
        
    def get_cost_info(self) -> Dict[str, Any]:
        """Get cost information using Claude Code's built-in /cost command"""
        try:
            print("💰 Getting cost information from Claude Code...")
            
            # Use claude with /cost command and JSON output
            result = subprocess.run([
                "claude", "--dangerously-skip-permissions", "--print", "--output-format", "json", 
                "/cost"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                try:
                    cost_data = json.loads(result.stdout)
                    print("✅ Retrieved cost data from Claude Code")
                    return cost_data
                except json.JSONDecodeError:
                    # Fallback to parsing text output
                    print("⚠️  JSON parsing failed, trying text parsing...")
                    return self._parse_cost_text(result.stdout)
            else:
                print(f"⚠️  /cost command failed: {result.stderr}")
                return {}
                
        except subprocess.TimeoutExpired:
            print("⚠️  Cost query timed out")
            return {}
        except Exception as e:
            print(f"❌ Error getting cost info: {e}")
            return {}
    
    def _parse_cost_text(self, text: str) -> Dict[str, Any]:
        """Parse cost information from text output"""
        cost_info = {
            "total_cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "raw_output": text
        }
        
        try:
            # Look for common cost patterns in the text
            lines = text.split('\n')
            for line in lines:
                line = line.lower().strip()
                
                # Look for cost amounts
                cost_match = re.search(r'\$?([\d.]+)', line)
                if cost_match and any(word in line for word in ['cost', 'total', 'spent']):
                    cost_info["total_cost"] = float(cost_match.group(1))
                
                # Look for token counts
                if 'input' in line and 'token' in line:
                    token_match = re.search(r'(\d+)', line)
                    if token_match:
                        cost_info["input_tokens"] = int(token_match.group(1))
                        
                if 'output' in line and 'token' in line:
                    token_match = re.search(r'(\d+)', line)
                    if token_match:
                        cost_info["output_tokens"] = int(token_match.group(1))
                        
        except Exception as e:
            print(f"⚠️  Error parsing cost text: {e}")
            
        return cost_info
    
    def get_git_stats(self) -> Dict[str, Any]:
        """Get git statistics (lines changed, files modified)"""
        stats = {
            "files_changed": 0,
            "lines_added": 0,
            "lines_deleted": 0,
            "total_lines_changed": 0,
            "commits_made": 0
        }
        
        try:
            # Check for changes
            status_result = subprocess.run([
                "git", "status", "--porcelain"
            ], capture_output=True, text=True)
            
            if status_result.stdout.strip():
                # Get diff stats
                diff_result = subprocess.run([
                    "git", "diff", "--stat", "HEAD"
                ], capture_output=True, text=True)
                
                if diff_result.returncode == 0 and diff_result.stdout:
                    summary_line = diff_result.stdout.strip().split('\n')[-1]
                    
                    # Parse insertions and deletions
                    insertion_match = re.search(r'(\d+) insertion', summary_line)
                    if insertion_match:
                        stats["lines_added"] = int(insertion_match.group(1))
                        
                    deletion_match = re.search(r'(\d+) deletion', summary_line)
                    if deletion_match:
                        stats["lines_deleted"] = int(deletion_match.group(1))
                        
                    files_match = re.search(r'(\d+) file', summary_line)
                    if files_match:
                        stats["files_changed"] = int(files_match.group(1))
                        
                stats["total_lines_changed"] = stats["lines_added"] + stats["lines_deleted"]
                
            # Count commits made in this session (rough estimate)
            log_result = subprocess.run([
                "git", "log", "--oneline", "--since=1 hour ago"
            ], capture_output=True, text=True)
            
            if log_result.returncode == 0:
                stats["commits_made"] = len([line for line in log_result.stdout.strip().split('\n') if line.strip()])
                
        except Exception as e:
            print(f"⚠️  Error getting git stats: {e}")
            
        return stats
    
    def save_session_info(self, cost_info: Dict[str, Any], git_stats: Dict[str, Any]) -> None:
        """Save session information to file"""
        session_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cost": cost_info,
            "git_stats": git_stats,
            "summary": {
                "total_cost": cost_info.get("total_cost", 0.0),
                "total_tokens": cost_info.get("input_tokens", 0) + cost_info.get("output_tokens", 0),
                "lines_changed": git_stats.get("total_lines_changed", 0),
                "files_changed": git_stats.get("files_changed", 0)
            }
        }
        
        try:
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            print(f"💾 Session info saved to {self.session_file}")
        except Exception as e:
            print(f"❌ Error saving session info: {e}")
    
    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """Load session information from file"""
        if not self.session_file.exists():
            return None
            
        try:
            with open(self.session_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading session info: {e}")
            return None
    
    def print_summary(self) -> None:
        """Print a formatted summary"""
        session_info = self.get_session_info()
        if not session_info:
            print("ℹ️  No session information available")
            return
            
        summary = session_info.get("summary", {})
        print("📊 Claude Session Summary:")
        print(f"  💰 Cost: ${summary.get('total_cost', 0):.4f}")
        print(f"  🔤 Tokens: {summary.get('total_tokens', 0):,}")
        print(f"  📝 Lines changed: {summary.get('lines_changed', 0)}")
        print(f"  📁 Files modified: {summary.get('files_changed', 0)}")
        
        if 'timestamp' in session_info:
            print(f"  ⏰ Session: {session_info['timestamp']}")


def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: claude_session_info.py <command>")
        print("Commands:")
        print("  collect    - Collect cost and git stats")
        print("  summary    - Show session summary")
        print("  json       - Output session data as JSON")
        sys.exit(1)
        
    session_info = ClaudeSessionInfo()
    command = sys.argv[1]
    
    if command == "collect":
        print("📊 Collecting session information...")
        cost_info = session_info.get_cost_info()
        git_stats = session_info.get_git_stats()
        session_info.save_session_info(cost_info, git_stats)
        session_info.print_summary()
        
    elif command == "summary":
        session_info.print_summary()
        
    elif command == "json":
        data = session_info.get_session_info()
        if data:
            print(json.dumps(data, indent=2))
        else:
            print("{}")
            
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()