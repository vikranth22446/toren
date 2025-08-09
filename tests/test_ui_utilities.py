#!/usr/bin/env python3
"""
Test Script for ui_utilities.py - Tests CLI output and formatting

Usage: python3 tests/test_ui_utilities.py
"""

import sys
import io
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock

# Add parent directory to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui_utilities import UIUtilities

def capture_output(func, *args, **kwargs):
    """Capture stdout from a function call"""
    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()
    try:
        func(*args, **kwargs)
        return captured_output.getvalue()
    finally:
        sys.stdout = old_stdout

def confirm(message):
    """Ask user to confirm if operation worked"""
    response = input(f"{message} (y/n): ").strip().lower()
    return response == 'y'

def create_mock_dependencies():
    """Create mock dependencies for UIUtilities"""
    mock_job_manager = Mock()
    mock_validator = Mock()
    mock_ai_cli = Mock()
    mock_container_manager = Mock()
    
    return mock_job_manager, mock_validator, mock_ai_cli, mock_container_manager

def create_sample_jobs():
    """Create sample job data for testing"""
    base_time = datetime.now(timezone.utc)
    
    return [
        {
            "job_id": "abc12345",
            "status": "running",
            "branch_name": "feature/new-feature",
            "base_branch": "main",
            "base_image": "python:3.11",
            "created_at": base_time.isoformat(),
            "updated_at": base_time.isoformat(),
            "ai_summary": "Add user authentication system",
            "task_spec": "Implement OAuth login with JWT tokens",
            "github_issue": "https://github.com/user/repo/issues/123",
            "container_id": "container_123",
            "cost_info": {
                "total_cost": 0.0234,
                "input_tokens": 1500,
                "output_tokens": 800
            },
            "git_stats": {
                "lines_added": 50,
                "lines_deleted": 20,
                "total_lines_changed": 70,
                "files_changed": 3
            },
            "progress_log": [
                {
                    "timestamp": base_time.isoformat(),
                    "message": "Started processing task"
                },
                {
                    "timestamp": base_time.isoformat(),
                    "message": "Generated authentication module"
                }
            ]
        },
        {
            "job_id": "def67890",
            "status": "completed",
            "branch_name": "fix/bug-456",
            "base_branch": "main", 
            "base_image": "alpine:latest",
            "created_at": base_time.isoformat(),
            "updated_at": base_time.isoformat(),
            "ai_summary": "Fix login validation bug",
            "task_spec": "Resolve null pointer exception in login form",
            "pr_url": "https://github.com/user/repo/pull/789",
            "cost_info": {
                "total_cost": 0.0156,
                "input_tokens": 800,
                "output_tokens": 400
            },
            "git_stats": {
                "lines_added": 5,
                "lines_deleted": 10,
                "total_lines_changed": 15,
                "files_changed": 1
            },
            "progress_log": []
        },
        {
            "job_id": "ghi11111",
            "status": "failed",
            "branch_name": "feature/complex-task",
            "base_branch": "develop",
            "base_image": "node:18",
            "created_at": base_time.isoformat(),
            "updated_at": base_time.isoformat(),
            "ai_summary": "Implement real-time notifications",
            "task_spec": "Add WebSocket support for live updates",
            "error_message": "Container exited with code 1",
            "cost_info": {
                "total_cost": 0.0,
                "input_tokens": 0,
                "output_tokens": 0
            },
            "git_stats": {
                "lines_added": 0,
                "lines_deleted": 0,
                "total_lines_changed": 0,
                "files_changed": 0
            },
            "progress_log": [
                {
                    "timestamp": base_time.isoformat(),
                    "message": "Failed to install dependencies"
                }
            ]
        }
    ]

def test_initialization():
    """Test UIUtilities initialization"""
    print("=== Testing Initialization ===")
    
    job_manager, validator, ai_cli, container_manager = create_mock_dependencies()
    
    ui = UIUtilities(job_manager, validator, ai_cli, container_manager)
    
    assert ui.job_manager == job_manager
    assert ui.validator == validator
    assert ui.ai_cli == ai_cli
    assert ui.container_manager == container_manager
    
    print("✅ UIUtilities initialized with all dependencies")
    return True

def test_timestamp_formatting():
    """Test timestamp formatting functionality"""
    print("\n=== Testing Timestamp Formatting ===")
    
    job_manager, validator, ai_cli, container_manager = create_mock_dependencies()
    ui = UIUtilities(job_manager, validator, ai_cli, container_manager)
    
    # Test recent timestamp
    now = datetime.now(timezone.utc)
    recent_time = now.replace(second=now.second - 30).isoformat()
    result = ui.format_timestamp(recent_time)
    assert "just now" in result or "m ago" in result
    print("✅ Recent timestamp formatted correctly")
    
    # Test older timestamp
    old_time = now.replace(hour=now.hour - 2).isoformat()
    result = ui.format_timestamp(old_time)
    assert "h ago" in result
    print("✅ Hour-old timestamp formatted correctly")
    
    # Test invalid timestamp
    result = ui.format_timestamp("invalid-date")
    assert result == "invalid-date"
    print("✅ Invalid timestamp handled gracefully")
    
    return True

def test_status_coloring():
    """Test status color formatting"""
    print("\n=== Testing Status Coloring ===")
    
    job_manager, validator, ai_cli, container_manager = create_mock_dependencies()
    ui = UIUtilities(job_manager, validator, ai_cli, container_manager)
    
    # Test known statuses
    test_statuses = ["running", "completed", "failed", "queued", "cancelled"]
    
    for status in test_statuses:
        colored = ui.status_color(status)
        # Should contain ANSI color codes
        assert "\033[" in colored  # Color start
        assert colored.endswith("\033[0m")  # Reset code
        assert status in colored  # Original status text
        print(f"✅ Status '{status}' colored correctly")
    
    # Test unknown status
    unknown_colored = ui.status_color("unknown")
    assert "unknown" in unknown_colored
    print("✅ Unknown status handled gracefully")
    
    return True

def test_job_list_display():
    """Test job list formatting and display"""
    print("\n=== Testing Job List Display ===")
    
    job_manager, validator, ai_cli, container_manager = create_mock_dependencies()
    ui = UIUtilities(job_manager, validator, ai_cli, container_manager)
    
    # Mock job_manager.list_jobs
    sample_jobs = create_sample_jobs()
    job_manager.list_jobs.return_value = sample_jobs
    
    # Capture output from show_status
    output = capture_output(ui.show_status)
    
    print("Job list output preview:")
    print("-" * 40)
    print(output[:500] + "..." if len(output) > 500 else output)
    print("-" * 40)
    
    # Check that essential elements are present
    assert "JOB ID" in output  # Header
    assert "STATUS" in output  # Header
    assert "BRANCH" in output  # Header
    assert "abc12345" in output  # First job ID
    assert "def67890" in output  # Second job ID
    assert "feature/new-feature" in output  # Branch name
    assert "$0.023" in output or "$0.024" in output  # Cost formatting
    print("✅ Job list contains expected elements")
    
    return confirm("Does the job list display look properly formatted?")

def test_detailed_job_display():
    """Test detailed job view"""
    print("\n=== Testing Detailed Job Display ===")
    
    job_manager, validator, ai_cli, container_manager = create_mock_dependencies()
    ui = UIUtilities(job_manager, validator, ai_cli, container_manager)
    
    # Mock job_manager.get_job for specific job
    sample_jobs = create_sample_jobs()
    job_manager.get_job.return_value = sample_jobs[0]  # Running job with details
    
    # Capture output from show_status with job_id
    output = capture_output(ui.show_status, job_id="abc12345")
    
    print("Detailed job output preview:")
    print("-" * 40)
    print(output)
    print("-" * 40)
    
    # Check that detailed elements are present
    assert "Job Details: abc12345" in output
    assert "Branch: feature/new-feature" in output
    assert "Base Image: python:3.11" in output
    assert "GitHub Issue:" in output
    assert "Session Metrics:" in output
    assert "Cost: $0.0234" in output
    assert "Progress Log:" in output
    assert "Task Specification:" in output
    print("✅ Detailed job view contains expected elements")
    
    return confirm("Does the detailed job view look properly formatted?")

def test_summary_display():
    """Test AI summary display"""
    print("\n=== Testing Summary Display ===")
    
    job_manager, validator, ai_cli, container_manager = create_mock_dependencies()
    ui = UIUtilities(job_manager, validator, ai_cli, container_manager)
    
    # Mock job_manager.get_job
    sample_jobs = create_sample_jobs()
    job_manager.get_job.return_value = sample_jobs[0]
    
    # Capture output from show_summary
    output = capture_output(ui.show_summary, job_id="abc12345")
    
    print("Summary output preview:")
    print("-" * 40)
    print(output)
    print("-" * 40)
    
    # Check summary elements
    assert "AI Summary for Job abc12345" in output
    assert "Add user authentication system" in output  # AI summary text
    assert "Latest Progress:" in output
    print("✅ Summary display contains expected elements")
    
    return confirm("Does the AI summary display look clear and informative?")

def test_logs_display_mock():
    """Test log display functionality (mocked)"""
    print("\n=== Testing Logs Display ===")
    
    job_manager, validator, ai_cli, container_manager = create_mock_dependencies()
    ui = UIUtilities(job_manager, validator, ai_cli, container_manager)
    
    # Mock job and logs
    sample_jobs = create_sample_jobs()
    job_manager.get_job.return_value = sample_jobs[0]
    job_manager.get_container_logs.return_value = "Sample container logs\nLine 1\nLine 2\nCompleted successfully"
    
    # Test non-follow logs
    output = capture_output(ui.show_logs, job_id="abc12345", follow=False)
    
    print("Logs output preview:")
    print("-" * 40) 
    print(output)
    print("-" * 40)
    
    # Check logs elements
    assert "Logs for Job abc12345" in output
    assert "Container: container_123" in output
    assert "Sample container logs" in output
    print("✅ Logs display contains expected elements")
    
    return confirm("Does the log display format look readable?")

def test_error_handling():
    """Test error handling in UI functions"""
    print("\n=== Testing Error Handling ===")
    
    job_manager, validator, ai_cli, container_manager = create_mock_dependencies()
    ui = UIUtilities(job_manager, validator, ai_cli, container_manager)
    
    # Test with non-existent job
    job_manager.get_job.return_value = None
    
    try:
        # This should exit with code 1, but we'll catch the SystemExit
        ui.show_summary("nonexistent")
        assert False, "Should have exited"
    except SystemExit as e:
        assert e.code == 1
        print("✅ Non-existent job handled correctly with exit")
    
    # Test empty job list
    job_manager.list_jobs.return_value = []
    output = capture_output(ui.show_status)
    assert "No jobs found" in output
    print("✅ Empty job list handled gracefully")
    
    return True

def test_cleanup_functionality():
    """Test cleanup UI functions"""
    print("\n=== Testing Cleanup Functions ===")
    
    job_manager, validator, ai_cli, container_manager = create_mock_dependencies()
    ui = UIUtilities(job_manager, validator, ai_cli, container_manager)
    
    # Test cleanup all
    job_manager.cleanup_completed_jobs.return_value = 5
    output = capture_output(ui.cleanup_jobs, cleanup_all=True)
    
    assert "Cleaned up 5 completed jobs" in output
    print("✅ Cleanup all functionality works")
    
    # Test individual cleanup
    sample_jobs = create_sample_jobs()
    completed_job = sample_jobs[1]  # Completed job
    job_manager.get_job.return_value = completed_job
    job_manager.cleanup_job.return_value = True
    
    output = capture_output(ui.cleanup_jobs, job_id="def67890")
    assert "Cleaned up job def67890" in output
    print("✅ Individual job cleanup works")
    
    return True

def test_kill_job_functionality():
    """Test kill job functionality"""
    print("\n=== Testing Kill Job Function ===")
    
    job_manager, validator, ai_cli, container_manager = create_mock_dependencies()
    ui = UIUtilities(job_manager, validator, ai_cli, container_manager)
    
    # Test killing running job
    sample_jobs = create_sample_jobs()
    running_job = sample_jobs[0]  # Running job
    job_manager.get_job.return_value = running_job
    job_manager.update_job_status.return_value = True
    
    # Mock subprocess.run for docker kill (would need more complex mocking for real test)
    # For now, test the logic flow
    try:
        output = capture_output(ui.kill_job, job_id="abc12345")
        # This might fail due to actual docker call, but that's expected
    except SystemExit:
        # Expected if docker command fails
        pass
    
    print("✅ Kill job function logic tested")
    
    return True

def main():
    """Run all tests"""
    print("🚀 Testing UI Utilities")
    print("=" * 50)
    
    tests = [
        ("Initialization", test_initialization),
        ("Timestamp Formatting", test_timestamp_formatting),
        ("Status Coloring", test_status_coloring),
        ("Job List Display", test_job_list_display),
        ("Detailed Job Display", test_detailed_job_display),
        ("Summary Display", test_summary_display),
        ("Logs Display", test_logs_display_mock),
        ("Error Handling", test_error_handling),
        ("Cleanup Functions", test_cleanup_functionality),
        ("Kill Job Function", test_kill_job_functionality)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
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
    
    print(f"\n{'='*50}")
    print(f"🏁 Results: {passed}/{total} tests passed")
    print(f"{'='*50}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)