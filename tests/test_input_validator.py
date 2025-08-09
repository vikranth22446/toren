#!/usr/bin/env python3
"""
Automated Test Script for input_validator.py - Pure validation logic testing
"""

import sys
import tempfile
from pathlib import Path
import argparse

# Add parent directory to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from input_validator import InputValidator

def test_branch_name_validation():
    """Test branch name sanitization"""
    print("=== Testing branch name validation ===")
    validator = InputValidator()
    
    # Valid cases
    valid_branches = [
        "feature/new-feature",
        "fix/bug-123", 
        "main",
        "dev",
        "feature.test",
        "fix_issue_123"
    ]
    
    for branch in valid_branches:
        try:
            result = validator.sanitize_branch_name(branch)
            assert result == branch
            print(f"✅ Valid branch: {branch}")
        except ValueError as e:
            print(f"❌ Should be valid: {branch} - {e}")
            return False
    
    # Invalid cases
    invalid_branches = [
        "",
        "branch with spaces",
        "branch..name",
        "-starts-with-dash",
        "ends-with-dash-",
        "branch~name",
        "branch^name",
        "branch:name",
        "branch[name]",
        "branch?name",
        "branch*name"
    ]
    
    for branch in invalid_branches:
        try:
            validator.sanitize_branch_name(branch)
            print(f"❌ Should be invalid: {branch}")
            return False
        except ValueError:
            print(f"✅ Correctly rejected: {branch}")
    
    return True

def test_docker_image_validation():
    """Test Docker image name validation"""
    print("\n=== Testing Docker image validation ===")
    validator = InputValidator()
    
    # Valid cases
    valid_images = [
        "python:3.11",
        "ubuntu",
        "registry.com/user/image:tag",
        "gcr.io/project/image",
        "python",
        "node:18-alpine"
    ]
    
    for image in valid_images:
        try:
            result = validator.sanitize_docker_image(image)
            assert result == image.lower()
            print(f"✅ Valid image: {image}")
        except ValueError as e:
            print(f"❌ Should be valid: {image} - {e}")
            return False
    
    # Invalid cases
    invalid_images = [
        "",
        "image;rm -rf /",
        "image && echo hello",
        "image|grep something",
        "image`whoami`",
        "image$USER",
        "image(test)",
        "image<test>",
        'image"test"',
        "image'test'",
        "a" * 201  # Too long
    ]
    
    for image in invalid_images:
        try:
            validator.sanitize_docker_image(image)
            print(f"❌ Should be invalid: {image}")
            return False
        except ValueError:
            print(f"✅ Correctly rejected: {image}")
    
    return True

def test_github_url_validation():
    """Test GitHub issue URL validation"""
    print("\n=== Testing GitHub URL validation ===")
    validator = InputValidator()
    
    # Valid cases
    valid_urls = [
        "https://github.com/user/repo/issues/123",
        "https://github.com/test-user/test-repo/issues/1",
        "https://github.com/user_name/repo.name/issues/9999"
    ]
    
    for url in valid_urls:
        try:
            result = validator.sanitize_github_issue_url(url)
            assert result == url
            print(f"✅ Valid URL: {url}")
        except ValueError as e:
            print(f"❌ Should be valid: {url} - {e}")
            return False
    
    # Invalid cases
    invalid_urls = [
        "",
        "not-a-url",
        "https://github.com/user/repo/pulls/123",  # PR not issue
        "https://gitlab.com/user/repo/issues/123",  # Wrong host
        "http://github.com/user/repo/issues/123",   # HTTP not HTTPS
        "https://github.com/user/repo/issues/abc",  # Non-numeric issue
        "a" * 501  # Too long
    ]
    
    for url in invalid_urls:
        try:
            validator.sanitize_github_issue_url(url)
            print(f"❌ Should be invalid: {url}")
            return False
        except ValueError:
            print(f"✅ Correctly rejected: {url}")
    
    return True

def test_pr_number_validation():
    """Test PR number validation"""
    print("\n=== Testing PR number validation ===")
    validator = InputValidator()
    
    # Valid cases - should return just the number
    valid_cases = [
        ("123", "123"),
        ("1", "1"),
        ("https://github.com/user/repo/pull/456", "456")
    ]
    
    for input_val, expected in valid_cases:
        try:
            result = validator.sanitize_pr_number(input_val)
            assert result == expected
            print(f"✅ Valid PR: {input_val} -> {result}")
        except ValueError as e:
            print(f"❌ Should be valid: {input_val} - {e}")
            return False
    
    # Invalid cases
    invalid_prs = [
        "",
        "abc",
        "12345678901",  # Too long
        "https://github.com/user/repo/issues/123",  # Issue not PR
        "not-a-number"
    ]
    
    for pr in invalid_prs:
        try:
            validator.sanitize_pr_number(pr)
            print(f"❌ Should be invalid: {pr}")
            return False
        except ValueError:
            print(f"✅ Correctly rejected: {pr}")
    
    return True

def test_env_var_validation():
    """Test environment variable validation"""
    print("\n=== Testing environment variable validation ===")
    validator = InputValidator()
    
    # Valid cases
    valid_env_vars = [
        "CUDA_VISIBLE_DEVICES=0",
        "PATH=/usr/bin",
        "HOME_DIR=/home/user",
        "DEBUG_MODE=true",
        "API_URL=https://api.example.com"
    ]
    
    for env_var in valid_env_vars:
        try:
            result = validator.validate_env_var(env_var)
            assert result == env_var
            print(f"✅ Valid env var: {env_var}")
        except ValueError as e:
            print(f"❌ Should be valid: {env_var} - {e}")
            return False
    
    # Invalid cases
    invalid_env_vars = [
        "",
        "NO_EQUALS",
        "=VALUE_NO_KEY",
        "lowercase=value",  # Key not uppercase
        "KEY;VALUE=test",   # Dangerous char in key
        "KEY=value;rm -rf /",  # Dangerous chars in value
        "KEY=value`whoami`",
        "KEY=value$(echo)",
        "KEY=value|grep",
        "KEY=value&echo",
        "A" * 101 + "=value",  # Key too long
        "KEY=" + "A" * 1001    # Value too long
    ]
    
    for env_var in invalid_env_vars:
        try:
            validator.validate_env_var(env_var)
            print(f"❌ Should be invalid: {env_var}")
            return False
        except ValueError:
            print(f"✅ Correctly rejected: {env_var}")
    
    return True

def test_task_spec_validation():
    """Test task specification validation"""
    print("\n=== Testing task spec validation ===")
    validator = InputValidator()
    
    # Valid cases
    valid_specs = [
        "Fix the bug in function X",
        "Add new feature Y\nWith multiple lines\nOf description",
        "Simple task"
    ]
    
    for spec in valid_specs:
        try:
            result = validator.validate_task_spec(spec)
            assert result == spec
            print(f"✅ Valid spec: {spec[:30]}...")
        except ValueError as e:
            print(f"❌ Should be valid spec - {e}")
            return False
    
    # Invalid cases
    invalid_specs = [
        "",  # Empty
        "A" * 50001,  # Too long
    ]
    
    for spec in invalid_specs:
        try:
            validator.validate_task_spec(spec)
            print(f"❌ Should be invalid spec")
            return False
        except ValueError:
            print(f"✅ Correctly rejected spec")
    
    return True

def test_spec_safety_validation():
    """Test spec safety checking"""
    print("\n=== Testing spec safety validation ===")
    validator = InputValidator()
    
    # Should flag potential security issues
    risky_specs = [
        "Please add my password 'secret123' to the config",
        "Use API key abc123 for authentication",
        "Store the secret token in the database",
        "Hardcode the credential in the file",
        "Expose the private key publicly"
    ]
    
    for spec in risky_specs:
        concerns = validator.validate_spec_safety(spec)
        if concerns:
            print(f"✅ Flagged security concern in: {spec[:30]}...")
        else:
            print(f"❌ Should have flagged: {spec[:30]}...")
            return False
    
    # Should not flag normal specs
    safe_specs = [
        "Fix the login function",
        "Add error handling to the API",
        "Update the documentation"
    ]
    
    for spec in safe_specs:
        concerns = validator.validate_spec_safety(spec)
        if not concerns:
            print(f"✅ No concerns for: {spec}")
        else:
            print(f"❌ False positive for: {spec}")
            return False
    
    return True

def test_mount_path_validation():
    """Test mount path validation"""
    print("\n=== Testing mount path validation ===")
    validator = InputValidator()
    
    # Create temporary files for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_file = temp_path / "test.txt"
        test_file.write_text("test")
        
        try:
            result = validator.validate_mount_path(test_file, "test file")
            print(f"✅ Valid mount path: {test_file}")
        except ValueError as e:
            print(f"❌ Should be valid: {test_file} - {e}")
            return False
    
    # Test non-existent path
    try:
        validator.validate_mount_path(Path("/nonexistent/path"), "test")
        print("❌ Should reject non-existent path")
        return False
    except ValueError:
        print("✅ Correctly rejected non-existent path")
    
    return True

def main():
    """Run all validation tests"""
    print("🚀 Running Input Validator Tests")
    print("=" * 50)
    
    tests = [
        ("Branch Name Validation", test_branch_name_validation),
        ("Docker Image Validation", test_docker_image_validation),
        ("GitHub URL Validation", test_github_url_validation),
        ("PR Number Validation", test_pr_number_validation),
        ("Environment Variable Validation", test_env_var_validation),
        ("Task Spec Validation", test_task_spec_validation),
        ("Spec Safety Validation", test_spec_safety_validation),
        ("Mount Path Validation", test_mount_path_validation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"\n✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"\n❌ {test_name} FAILED")
        except Exception as e:
            print(f"\n❌ {test_name} CRASHED: {e}")
    
    print(f"\n{'='*50}")
    print(f"🏁 Results: {passed}/{total} tests passed")
    print(f"{'='*50}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)