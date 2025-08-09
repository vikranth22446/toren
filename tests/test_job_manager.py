#!/usr/bin/env python3
"""
Test Script for job_manager.py - Tests job lifecycle and file operations

Usage: python3 tests/test_job_manager.py
"""

import sys
import os
import json
import tempfile
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_manager import JobManager

def confirm(message):
    """Ask user to confirm if operation worked"""
    response = input(f"{message} (y/n): ").strip().lower()
    return response == 'y'

def setup_test_job_manager():
    """Create a JobManager with temporary directory for testing"""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_job_manager_"))
    
    # Monkey patch the jobs_dir to use our temp directory
    job_manager = JobManager()
    job_manager.jobs_dir = temp_dir / "jobs"
    job_manager.jobs_dir.mkdir(parents=True, exist_ok=True)
    
    return job_manager, temp_dir

def test_initialization():
    """Test JobManager initialization"""
    print("=== Testing Initialization ===")
    
    jm, temp_dir = setup_test_job_manager()
    
    # Check that jobs directory was created
    assert jm.jobs_dir.exists()
    assert jm.jobs_dir.is_dir()
    print("✅ Jobs directory created successfully")
    
    # Check constants are properly set
    assert jm.MAX_JSON_SIZE > 0
    assert len(jm.REQUIRED_JOB_KEYS) > 0
    assert len(jm.VALID_STATUSES) > 0
    print("✅ Constants properly initialized")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    return True

def test_job_creation():
    """Test job creation and data validation"""
    print("\n=== Testing Job Creation ===")
    
    jm, temp_dir = setup_test_job_manager()
    
    try:
        # Create a test job
        job_id = jm.create_job(
            task_spec="Test task specification",
            base_image="python:3.11", 
            branch_name="test-branch",
            base_branch="main",
            github_issue="https://github.com/user/repo/issues/123"
        )
        
        assert job_id is not None
        assert len(job_id) == 8  # UUID first 8 characters
        print(f"✅ Job created with ID: {job_id}")
        
        # Check job file exists
        job_file = jm.jobs_dir / f"{job_id}.json"
        assert job_file.exists()
        print("✅ Job file created")
        
        # Load and validate job data
        job_data = jm.get_job(job_id)
        assert job_data is not None
        print("✅ Job data retrieved successfully")
        
        # Check required fields
        for field in jm.REQUIRED_JOB_KEYS:
            assert field in job_data
        print("✅ All required fields present")
        
        # Check specific values
        assert job_data["task_spec"] == "Test task specification"
        assert job_data["base_image"] == "python:3.11"
        assert job_data["branch_name"] == "test-branch"
        assert job_data["base_branch"] == "main"
        assert job_data["status"] == "queued"
        print("✅ Job data values correct")
        
        # Check AI summary was generated
        assert "ai_summary" in job_data
        assert len(job_data["ai_summary"]) > 0
        print(f"✅ AI summary generated: {job_data['ai_summary']}")
        
        return True
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)

def test_job_status_updates():
    """Test job status updates and progress tracking"""
    print("\n=== Testing Job Status Updates ===")
    
    jm, temp_dir = setup_test_job_manager()
    
    try:
        # Create test job
        job_id = jm.create_job(
            task_spec="Status update test",
            base_image="alpine:latest",
            branch_name="status-test",
            base_branch="main"
        )
        
        # Test status update
        success = jm.update_job_status(
            job_id, 
            "running",
            container_id="test-container-123",
            progress_message="Started processing"
        )
        assert success == True
        print("✅ Status update successful")
        
        # Verify update
        job_data = jm.get_job(job_id)
        assert job_data["status"] == "running"
        assert job_data["container_id"] == "test-container-123"
        assert len(job_data["progress_log"]) == 1
        assert "Started processing" in job_data["progress_log"][0]["message"]
        print("✅ Status and progress updated correctly")
        
        # Test multiple progress updates
        jm.update_job_status(job_id, "running", progress_message="Step 1 complete")
        jm.update_job_status(job_id, "running", progress_message="Step 2 complete")
        
        job_data = jm.get_job(job_id)
        assert len(job_data["progress_log"]) == 3
        print("✅ Multiple progress updates work")
        
        # Test completion with PR URL
        success = jm.update_job_status(
            job_id,
            "completed", 
            pr_url="https://github.com/user/repo/pull/456"
        )
        assert success == True
        
        job_data = jm.get_job(job_id)
        assert job_data["status"] == "completed"
        assert job_data["pr_url"] == "https://github.com/user/repo/pull/456"
        print("✅ Completion status with PR URL works")
        
        return True
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)

def test_cost_info_updates():
    """Test cost and git statistics updates"""
    print("\n=== Testing Cost Info Updates ===")
    
    jm, temp_dir = setup_test_job_manager()
    
    try:
        # Create test job
        job_id = jm.create_job(
            task_spec="Cost info test",
            base_image="python:3.11",
            branch_name="cost-test", 
            base_branch="main"
        )
        
        # Test cost info update
        cost_info = {
            "total_cost": 0.0234,
            "input_tokens": 1500,
            "output_tokens": 800,
            "session_duration": 120
        }
        
        git_stats = {
            "lines_added": 50,
            "lines_deleted": 20,
            "total_lines_changed": 70,
            "files_changed": 3,
            "commits_made": 2
        }
        
        success = jm.update_job_cost_info(job_id, cost_info, git_stats)
        assert success == True
        print("✅ Cost info update successful")
        
        # Verify update
        job_data = jm.get_job(job_id)
        assert job_data["cost_info"]["total_cost"] == 0.0234
        assert job_data["cost_info"]["input_tokens"] == 1500
        assert job_data["git_stats"]["lines_added"] == 50
        assert job_data["git_stats"]["files_changed"] == 3
        print("✅ Cost and git stats updated correctly")
        
        return True
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)

def test_job_listing_and_filtering():
    """Test job listing and status filtering"""
    print("\n=== Testing Job Listing ===")
    
    jm, temp_dir = setup_test_job_manager()
    
    try:
        # Create multiple test jobs with different statuses
        job_ids = []
        
        job_ids.append(jm.create_job("Task 1", "python:3.11", "branch1", "main"))
        job_ids.append(jm.create_job("Task 2", "alpine:latest", "branch2", "main"))  
        job_ids.append(jm.create_job("Task 3", "node:18", "branch3", "main"))
        
        # Update statuses
        jm.update_job_status(job_ids[0], "running")
        jm.update_job_status(job_ids[1], "completed")
        jm.update_job_status(job_ids[2], "failed")
        
        # Test listing all jobs
        all_jobs = jm.list_jobs()
        assert len(all_jobs) == 3
        print("✅ All jobs listed correctly")
        
        # Test filtering by status
        running_jobs = jm.list_jobs(status_filter="running")
        assert len(running_jobs) == 1
        assert running_jobs[0]["job_id"] == job_ids[0]
        print("✅ Status filtering works")
        
        completed_jobs = jm.list_jobs(status_filter="completed")
        assert len(completed_jobs) == 1
        assert completed_jobs[0]["job_id"] == job_ids[1]
        print("✅ Completed job filtering works")
        
        failed_jobs = jm.list_jobs(status_filter="failed")
        assert len(failed_jobs) == 1
        assert failed_jobs[0]["job_id"] == job_ids[2]
        print("✅ Failed job filtering works")
        
        # Check sorting (newest first)
        assert all_jobs[0]["job_id"] == job_ids[2]  # Last created
        assert all_jobs[2]["job_id"] == job_ids[0]  # First created
        print("✅ Jobs sorted correctly by creation time")
        
        return True
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)

def test_file_locking_and_atomic_operations():
    """Test file locking and atomic write operations"""
    print("\n=== Testing File Operations ===")
    
    jm, temp_dir = setup_test_job_manager()
    
    try:
        # Create test job
        job_id = jm.create_job("File ops test", "python:3.11", "file-test", "main")
        
        # Test that lock files work
        with jm._lock_job_file(job_id):
            # Check lock file exists during lock
            lock_file = jm.jobs_dir / f"{job_id}.lock"
            # Lock file might not be visible due to implementation
            pass
        
        # Lock file should be cleaned up
        lock_file = jm.jobs_dir / f"{job_id}.lock"
        assert not lock_file.exists()
        print("✅ Lock file cleanup works")
        
        # Test atomic write
        test_file = temp_dir / "atomic_test.json"
        test_data = {"test": "data", "number": 42}
        
        with jm._atomic_write(test_file) as temp_file:
            with open(temp_file, 'w') as f:
                json.dump(test_data, f)
        
        # File should exist and contain correct data
        assert test_file.exists()
        with open(test_file) as f:
            loaded_data = json.load(f)
        assert loaded_data == test_data
        print("✅ Atomic write operations work")
        
        return True
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)

def test_data_validation():
    """Test job data validation"""
    print("\n=== Testing Data Validation ===")
    
    jm, temp_dir = setup_test_job_manager()
    
    try:
        # Test valid job data
        valid_data = {
            "job_id": "test123",
            "status": "queued",
            "task_spec": "Test task",
            "branch_name": "test-branch",
            "base_branch": "main", 
            "base_image": "python:3.11",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "progress_log": []
        }
        
        assert jm._validate_job_data(valid_data) == True
        print("✅ Valid job data passes validation")
        
        # Test invalid job data - missing required fields
        invalid_data = {
            "job_id": "test123",
            "status": "queued"
            # Missing other required fields
        }
        
        assert jm._validate_job_data(invalid_data) == False
        print("✅ Invalid job data fails validation")
        
        # Test invalid status
        invalid_status_data = valid_data.copy()
        invalid_status_data["status"] = "invalid_status"
        
        assert jm._validate_job_data(invalid_status_data) == False
        print("✅ Invalid status fails validation")
        
        # Test non-string fields
        invalid_type_data = valid_data.copy()
        invalid_type_data["job_id"] = 123  # Should be string
        
        assert jm._validate_job_data(invalid_type_data) == False
        print("✅ Invalid field types fail validation")
        
        return True
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)

def test_job_cleanup():
    """Test job cleanup functionality"""  
    print("\n=== Testing Job Cleanup ===")
    
    jm, temp_dir = setup_test_job_manager()
    
    try:
        # Create test jobs
        job_id1 = jm.create_job("Cleanup test 1", "python:3.11", "cleanup1", "main")
        job_id2 = jm.create_job("Cleanup test 2", "alpine:latest", "cleanup2", "main") 
        
        # Mark one as completed, one as failed
        jm.update_job_status(job_id1, "completed")
        jm.update_job_status(job_id2, "failed")
        
        # Verify jobs exist
        assert jm.get_job(job_id1) is not None
        assert jm.get_job(job_id2) is not None
        
        # Test individual job cleanup
        success = jm.cleanup_job(job_id1)
        assert success == True
        print("✅ Individual job cleanup successful")
        
        # Job should be gone
        assert jm.get_job(job_id1) is None
        print("✅ Cleaned up job removed")
        
        # Other job should still exist
        assert jm.get_job(job_id2) is not None
        print("✅ Other jobs unaffected")
        
        # Test cleanup of all completed jobs
        jm.update_job_status(job_id2, "completed")
        cleaned_count = jm.cleanup_completed_jobs()
        assert cleaned_count == 1
        print("✅ Bulk cleanup of completed jobs works")
        
        return True
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)

def test_error_handling():
    """Test error handling for edge cases"""
    print("\n=== Testing Error Handling ===")
    
    jm, temp_dir = setup_test_job_manager()
    
    try:
        # Test operations on non-existent job
        result = jm.get_job("nonexistent")
        assert result is None
        print("✅ Non-existent job returns None")
        
        result = jm.update_job_status("nonexistent", "running")
        assert result == False
        print("✅ Update on non-existent job fails gracefully")
        
        result = jm.cleanup_job("nonexistent") 
        assert result == False
        print("✅ Cleanup on non-existent job fails gracefully")
        
        # Test with corrupted job file
        job_id = jm.create_job("Corruption test", "python:3.11", "corrupt", "main")
        job_file = jm.jobs_dir / f"{job_id}.json"
        
        # Corrupt the file
        job_file.write_text("invalid json content")
        
        result = jm.get_job(job_id)
        assert result is None
        print("✅ Corrupted job file handled gracefully")
        
        return True
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)

def test_concurrent_operations():
    """Test thread safety of job operations"""
    print("\n=== Testing Concurrent Operations ===")
    
    jm, temp_dir = setup_test_job_manager()
    
    try:
        # Create a job for concurrent testing
        job_id = jm.create_job("Concurrency test", "python:3.11", "concurrent", "main")
        
        # Track results from multiple threads
        results = []
        errors = []
        
        def update_status(thread_id):
            try:
                for i in range(5):
                    success = jm.update_job_status(
                        job_id, 
                        "running",
                        progress_message=f"Thread {thread_id} update {i}"
                    )
                    results.append((thread_id, i, success))
                    time.sleep(0.01)  # Small delay
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=update_status, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5)
        
        # Check results
        assert len(errors) == 0, f"Concurrent operations had errors: {errors}"
        print("✅ No errors in concurrent operations")
        
        # Verify final state is consistent
        job_data = jm.get_job(job_id)
        assert job_data is not None
        assert len(job_data["progress_log"]) == 15  # 3 threads * 5 updates each
        print("✅ All concurrent updates recorded")
        
        # Check that we have progress messages from all threads
        messages = [log["message"] for log in job_data["progress_log"]]
        thread_counts = [0, 0, 0]
        for msg in messages:
            if "Thread 0" in msg:
                thread_counts[0] += 1
            elif "Thread 1" in msg:
                thread_counts[1] += 1  
            elif "Thread 2" in msg:
                thread_counts[2] += 1
        
        assert all(count == 5 for count in thread_counts)
        print("✅ All threads completed their updates")
        
        return True
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)

def main():
    """Run all tests"""
    print("🚀 Testing Job Manager")
    print("=" * 50)
    
    tests = [
        ("Initialization", test_initialization),
        ("Job Creation", test_job_creation),
        ("Status Updates", test_job_status_updates),
        ("Cost Info Updates", test_cost_info_updates),
        ("Job Listing", test_job_listing_and_filtering),
        ("File Operations", test_file_locking_and_atomic_operations),
        ("Data Validation", test_data_validation),
        ("Job Cleanup", test_job_cleanup),
        ("Error Handling", test_error_handling),
        ("Concurrent Operations", test_concurrent_operations)
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