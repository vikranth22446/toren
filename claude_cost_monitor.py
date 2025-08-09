#!/usr/bin/env python3
"""
Claude Cost Monitor - Real-time cost tracking during Claude execution
"""

import json
import subprocess
import threading
import time
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


class ClaudeCostMonitor:
    def __init__(self, update_interval: int = 30):
        self.update_interval = update_interval
        self.cost_file = Path("/tmp/claude_cost_monitor.json")
        self.monitoring = False
        self.monitor_thread = None
        self.session_start = datetime.now(timezone.utc)
        
    def get_current_cost(self) -> Dict[str, Any]:
        """Get current cost using correct claude command"""
        try:
            # Use claude --print --output-format json "/cost"  
            result = subprocess.run([
                "claude", "--print", "--output-format", "json", "/cost"
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    # Fallback to text parsing
                    return self._parse_cost_text(result.stdout)
            else:
                print(f"⚠️  Cost query failed: {result.stderr}")
                return {}
                
        except subprocess.TimeoutExpired:
            print("⚠️  Cost query timed out")
            return {}
        except Exception as e:
            print(f"⚠️  Error getting cost: {e}")
            return {}
    
    def _parse_cost_text(self, text: str) -> Dict[str, Any]:
        """Parse cost from text output if JSON fails"""
        import re
        
        cost_info = {"total_cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        
        # Look for cost patterns
        cost_match = re.search(r'\$?([\d.]+)', text)
        if cost_match:
            cost_info["total_cost"] = float(cost_match.group(1))
            
        # Look for token patterns
        input_match = re.search(r'input.*?(\d+)', text, re.IGNORECASE)
        if input_match:
            cost_info["input_tokens"] = int(input_match.group(1))
            
        output_match = re.search(r'output.*?(\d+)', text, re.IGNORECASE)  
        if output_match:
            cost_info["output_tokens"] = int(output_match.group(1))
            
        return cost_info
    
    def update_cost_data(self) -> None:
        """Update cost data and save to file"""
        cost_data = self.get_current_cost()
        git_stats = self.get_git_stats()
        
        session_data = {
            "session_start": self.session_start.isoformat(),
            "last_update": datetime.now(timezone.utc).isoformat(),
            "cost": cost_data,
            "git_stats": git_stats,
            "summary": {
                "total_cost": cost_data.get("total_cost", 0.0),
                "total_tokens": cost_data.get("input_tokens", 0) + cost_data.get("output_tokens", 0),
                "lines_changed": git_stats.get("total_lines_changed", 0),
                "files_changed": git_stats.get("files_changed", 0)
            }
        }
        
        try:
            with open(self.cost_file, 'w') as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            print(f"⚠️  Error saving cost data: {e}")
    
    def get_git_stats(self) -> Dict[str, Any]:
        """Get current git statistics"""
        stats = {
            "files_changed": 0,
            "lines_added": 0, 
            "lines_deleted": 0,
            "total_lines_changed": 0
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
                    import re
                    summary_line = diff_result.stdout.strip().split('\n')[-1]
                    
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
                
        except Exception as e:
            print(f"⚠️  Error getting git stats: {e}")
            
        return stats
    
    def monitor_loop(self) -> None:
        """Background monitoring loop"""
        while self.monitoring:
            try:
                self.update_cost_data()
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"⚠️  Error in monitor loop: {e}")
                time.sleep(self.update_interval)
    
    def start_monitoring(self) -> None:
        """Start background cost monitoring"""
        if self.monitoring:
            return
            
        print(f"📊 Starting real-time cost monitoring (updates every {self.update_interval}s)")
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        # Initial update
        self.update_cost_data()
    
    def stop_monitoring(self) -> None:
        """Stop background cost monitoring"""
        if not self.monitoring:
            return
            
        print("📊 Stopping cost monitoring...")
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        # Final update
        self.update_cost_data()
    
    def get_session_data(self) -> Optional[Dict[str, Any]]:
        """Get current session data"""
        if not self.cost_file.exists():
            return None
            
        try:
            with open(self.cost_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error reading session data: {e}")
            return None
    
    def print_summary(self) -> None:
        """Print current session summary"""
        data = self.get_session_data()
        if not data:
            print("ℹ️  No session data available")
            return
            
        summary = data.get("summary", {})
        print("📈 Current Session:")
        print(f"  💰 Cost: ${summary.get('total_cost', 0):.4f}")
        print(f"  🔤 Tokens: {summary.get('total_tokens', 0):,}")
        print(f"  📝 Lines changed: {summary.get('lines_changed', 0)}")
        print(f"  📁 Files modified: {summary.get('files_changed', 0)}")


def main():
    """CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: claude_cost_monitor.py <command>")
        print("Commands:")
        print("  start [interval]  - Start monitoring (default 30s interval)")
        print("  stop             - Stop monitoring")
        print("  status           - Show current status")
        print("  summary          - Show session summary")
        print("  json             - Output session data as JSON")
        sys.exit(1)
        
    command = sys.argv[1]
    monitor = ClaudeCostMonitor()
    
    if command == "start":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        monitor = ClaudeCostMonitor(interval)
        monitor.start_monitoring()
        
        try:
            # Keep running until interrupted
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            monitor.stop_monitoring()
            
    elif command == "stop":
        monitor.stop_monitoring()
        
    elif command == "status":
        monitor.update_cost_data()
        monitor.print_summary()
        
    elif command == "summary":
        monitor.print_summary()
        
    elif command == "json":
        data = monitor.get_session_data()
        if data:
            print(json.dumps(data, indent=2))
        else:
            print("{}")
            
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()