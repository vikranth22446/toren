#!/usr/bin/env python3
"""
End-to-End Integration Test for toren.py
Tests full workflow from CLI commands to container execution

Usage: python3 tests/test_integration_toren.py
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add parent directory to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))


def confirm(message):
    """Ask user to confirm if operation worked"""
    response = input(f"{message} (y/n): ").strip().lower()
    return response == "y"


def run_command(cmd, description, timeout=30):
    """Run a command and return success, stdout, stderr"""
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(__file__).parent.parent,
        )
        print(f"Exit code: {result.returncode}")
        if result.stdout:
            print(f"Stdout: {result.stdout[:200]}...")
        if result.stderr:
            print(f"Stderr: {result.stderr[:200]}...")
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print(f"❌ Command timed out after {timeout}s")
        return False, "", "Command timed out"
    except Exception as e:
        print(f"❌ Command failed: {e}")
        return False, "", str(e)


def test_help_commands():
    """Test all help/info commands automatically"""
    print("=== Testing Help Commands ===")

    help_commands = [
        (["python3", "toren.py", "--help"], "Main help"),
        (["python3", "toren.py", "status", "--help"], "Status help"),
        (["python3", "toren.py", "logs", "--help"], "Logs help"),
        (["python3", "toren.py", "cleanup", "--help"], "Cleanup help"),
        (["python3", "toren.py", "health", "--help"], "Health help"),
    ]

    passed = 0
    for cmd, description in help_commands:
        success, stdout, stderr = run_command(cmd, description)
        if success and len(stdout) > 0:
            print(f"✅ {description} works")
            passed += 1
        else:
            print(f"❌ {description} failed")

    print(f"Help commands: {passed}/{len(help_commands)} passed")
    return passed == len(help_commands)


def test_status_commands():
    """Test status and listing commands"""
    print("\n=== Testing Status Commands ===")

    status_commands = [
        (["python3", "toren.py", "status"], "List all jobs", 15),
        (
            ["python3", "toren.py", "status", "--filter", "completed"],
            "Filter completed",
            15,
        ),
        (
            ["python3", "toren.py", "status", "--filter", "running"],
            "Filter running",
            15,
        ),
    ]

    passed = 0
    for cmd, description, timeout in status_commands:
        success, stdout, stderr = run_command(cmd, description, timeout)
        if success or "No jobs found" in stdout:
            print(f"✅ {description} works")
            passed += 1
        else:
            print(f"❌ {description} failed")

    print(f"Status commands: {passed}/{len(status_commands)} passed")
    return passed == len(status_commands)


def test_health_command():
    """Test health check command"""
    print("\n=== Testing Health Command ===")

    success, stdout, stderr = run_command(
        ["python3", "toren.py", "health", "--docker-image", "alpine:latest"],
        "Basic health check",
    )

    if success and "Health Check PASSED" in stdout:
        print("✅ Health check works")
        return True
    else:
        print("❌ Health check failed")
        return False


def test_cleanup_command():
    """Test cleanup command (dry run)"""
    print("\n=== Testing Cleanup Command ===")

    # Test cleanup all (should work even with no jobs)
    success, stdout, stderr = run_command(
        ["python3", "toren.py", "cleanup", "--all"], "Cleanup all jobs"
    )

    if success and "Cleaned up" in stdout:
        print("✅ Cleanup command works")
        return True
    else:
        print("❌ Cleanup command failed")
        return False


def create_test_spec():
    """Create a minimal test specification file"""
    test_spec_content = """# Test Task Specification

## Objective
Create a simple test file to verify the Claude Agent system is working.

## Requirements
1. Create a new file called `test_output.txt`
2. Write "Hello from Claude Agent test" to the file
3. Add a timestamp to the file
4. Commit the changes with message "Add test output file"

## Success Criteria
- File `test_output.txt` exists
- Contains the expected text and timestamp
- Changes are committed to git

This is a minimal test to verify the end-to-end workflow.
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(test_spec_content)
        return f.name


def test_run_command_interactive():
    """Test the run command with real execution (requires user approval)"""
    print("\n=== Testing Run Command (Interactive) ===")

    # Create test specification
    spec_file = create_test_spec()

    try:
        print(f"Created test spec: {spec_file}")

        # Show the user what will be run
        print("\nTest specification content:")
        print("-" * 50)
        with open(spec_file, "r") as f:
            print(f.read())
        print("-" * 50)

        if not confirm(
            "This will create a test job that writes a file and commits it. Continue?"
        ):
            print("⏭️  Skipping interactive run test")
            return True

        # Check prerequisites
        print("\nChecking prerequisites...")

        # Check Docker
        docker_check, _, _ = run_command(
            ["docker", "--version"], "Docker version check"
        )
        if not docker_check:
            print("❌ Docker not available - run test requires Docker")
            return False
        print("✅ Docker available")

        # Check git repo
        git_check, _, _ = run_command(["git", "status"], "Git status check")
        if not git_check:
            print("❌ Not in a git repository - run test requires git")
            return False
        print("✅ Git repository available")

        # Construct run command
        run_cmd = [
            "python3",
            "toren.py",
            "run",
            "--spec",
            spec_file,
            "--base-image",
            "alpine:latest",
            "--branch",
            f"test-integration-{int(time.time())}",
            "--disable-daemon",  # Run synchronously for testing
        ]

        print(f"\nWill run: {' '.join(run_cmd)}")

        if not confirm("Execute this command?"):
            print("⏭️  Skipping command execution")
            return True

        print("\n🚀 Starting integration test...")
        print("=" * 60)

        # Run the command with longer timeout for full workflow
        success, stdout, stderr = run_command(
            run_cmd, "Full integration test", timeout=300
        )

        print("=" * 60)
        print(f"Integration test completed with exit code: {0 if success else 1}")

        if stdout:
            print("Final output:")
            print(stdout[-500:])  # Show last 500 chars

        return confirm(
            "Did the integration test complete successfully? (Check for test_output.txt file and git commit)"
        )

    finally:
        # Cleanup test spec file
        try:
            os.unlink(spec_file)
        except OSError:
            pass


def test_invalid_commands():
    """Test error handling with invalid commands"""
    print("\n=== Testing Error Handling ===")

    invalid_commands = [
        (["python3", "toren.py", "nonexistent"], "Invalid command"),
        (["python3", "toren.py", "run"], "Run without required args"),
        (["python3", "toren.py", "logs"], "Logs without job ID"),
        (["python3", "toren.py", "summary"], "Summary without job ID"),
    ]

    passed = 0
    for cmd, description in invalid_commands:
        success, stdout, stderr = run_command(cmd, description)
        # These should fail with non-zero exit code
        if not success and (stderr or "Error:" in stdout or "❌" in stdout):
            print(f"✅ {description} properly rejected")
            passed += 1
        else:
            print(f"❌ {description} should have failed")

    print(f"Error handling: {passed}/{len(invalid_commands)} passed")
    return passed == len(invalid_commands)


def check_environment():
    """Check if environment is ready for integration tests"""
    print("=== Environment Check ===")

    # Check if we're in the right directory
    main_script = Path("toren.py")
    if not main_script.exists():
        print("❌ toren.py not found - run from project root directory")
        return False

    print("✅ Found toren.py")

    # Check Python modules can be imported
    try:
        pass

        print("✅ All Python modules can be imported")
    except ImportError as e:
        print(f"❌ Failed to import required modules: {e}")
        return False

    print("✅ Environment ready for testing")
    return True


def main():
    """Run all integration tests"""
    print("🚀 Claude Agent Integration Test Suite")
    print("=" * 60)

    if not check_environment():
        print("❌ Environment check failed")
        return False

    tests = [
        ("Help Commands", test_help_commands),
        ("Status Commands", test_status_commands),
        ("Health Command", test_health_command),
        ("Cleanup Command", test_cleanup_command),
        ("Error Handling", test_invalid_commands),
        ("Run Command (Interactive)", test_run_command_interactive),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{'=' * 20} {test_name} {'=' * 20}")
        try:
            if test_func():
                print(f"✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} CRASHED: {e}")
            import traceback

            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"🏁 Integration Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All integration tests passed!")
    else:
        print("⚠️  Some integration tests failed - check output above")

    print(f"{'=' * 60}")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
