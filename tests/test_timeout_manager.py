#!/usr/bin/env python3
"""
Minimal test for TimeoutManager functionality
"""

import os
import subprocess
import sys
import time
import tempfile
from pathlib import Path

# Add container lib to path for TimeoutManager import
container_lib_path = Path(__file__).parent.parent / "container" / "lib"
sys.path.insert(0, str(container_lib_path))

from ai_executor import TimeoutManager


def test_timeout_basic():
    """Test basic timeout functionality with a long-running command"""
    # Create a simple long-running process that sleeps for 30 seconds
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('import time; time.sleep(30); print("Should not reach here")')
        script_path = f.name
    
    try:
        # Start process that should timeout
        process = subprocess.Popen([sys.executable, script_path])
        
        # Set 2 second timeout
        timeout_manager = TimeoutManager(2, process)
        timeout_manager.start()
        
        # Wait for process to complete or timeout
        start_time = time.time()
        process.wait()
        elapsed_time = time.time() - start_time
        
        # Verify timeout occurred
        assert timeout_manager.is_timeout, "Timeout should have occurred"
        assert elapsed_time < 10, "Process should have been terminated quickly"
        assert process.returncode != 0, "Process should not have completed successfully"
        
        print("✅ Timeout test passed - process was terminated within time limit")
        
    finally:
        # Clean up
        if process.poll() is None:
            process.terminate()
        os.unlink(script_path)


if __name__ == "__main__":
    print("🧪 Testing TimeoutManager...")
    test_timeout_basic()
    print("✅ All timeout tests passed")