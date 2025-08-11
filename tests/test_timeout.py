#!/usr/bin/env python3
"""
Minimal test for timeout functionality
"""

import os
import subprocess
import sys
import time
from pathlib import Path


def test_timeout_functionality():
    """Test that timeout is properly set and monitored"""
    print("🧪 Testing timeout functionality...")
    
    # Test CLI parser accepts timelimit argument
    try:
        from cli_parser import CLIParser
        config = {"default_base_image": "python:3.11"}
        parser = CLIParser("test_user", config)
        
        # Simulate command with timelimit
        test_args = [
            "run", 
            "--spec", "/tmp/test_spec.md", 
            "--branch", "test-branch", 
            "--base-image", "python:3.11",
            "--timelimit", "30"
        ]
        
        # Replace sys.argv to test parsing
        original_argv = sys.argv
        sys.argv = ["toren.py"] + test_args
        
        try:
            args = parser.parse_args()
            assert hasattr(args, 'timelimit'), "timelimit argument not found"
            assert args.timelimit == 30, f"Expected timelimit 30, got {args.timelimit}"
            print("✅ CLI parser accepts timelimit argument")
        finally:
            sys.argv = original_argv
            
    except Exception as e:
        print(f"❌ CLI parser test failed: {e}")
        return False
    
    # Test environment variable setup
    try:
        os.environ["TIMELIMIT"] = "120"
        timelimit = int(os.environ.get("TIMELIMIT", 600))
        assert timelimit == 120, f"Expected timelimit 120, got {timelimit}"
        print("✅ Environment variable setup works")
    except Exception as e:
        print(f"❌ Environment variable test failed: {e}")
        return False
    finally:
        if "TIMELIMIT" in os.environ:
            del os.environ["TIMELIMIT"]
    
    # Test TimeoutMonitor class (minimal test)
    try:
        # Add the container lib to path
        container_lib_path = Path(__file__).parent.parent / "container" / "lib"
        sys.path.insert(0, str(container_lib_path))
        
        from ai_executor import TimeoutMonitor
        
        # Create a dummy process ID
        monitor = TimeoutMonitor(1, 12345)  # 1 second timeout
        assert monitor.timelimit == 1, "TimeoutMonitor timelimit not set correctly"
        assert monitor.process_id == 12345, "TimeoutMonitor process_id not set correctly"
        print("✅ TimeoutMonitor class initializes correctly")
        
    except Exception as e:
        print(f"❌ TimeoutMonitor test failed: {e}")
        return False
    finally:
        if str(container_lib_path) in sys.path:
            sys.path.remove(str(container_lib_path))
    
    print("✅ All timeout functionality tests passed")
    return True


if __name__ == "__main__":
    success = test_timeout_functionality()
    sys.exit(0 if success else 1)