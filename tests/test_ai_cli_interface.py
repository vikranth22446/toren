#!/usr/bin/env python3
"""
Test Script for ai_cli_interface.py - Tests with real Claude API calls

Usage:
1. Ensure ANTHROPIC_API_KEY is set in environment
2. Run: python3 tests/test_ai_cli_interface.py
"""

from ai_cli_interface import AICliInterface
import os
import sys
from pathlib import Path

# Add parent directory to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))


# Sample task specifications for testing
SAMPLE_TASKS = {
    "simple": "Fix a typo in the README file",
    "medium": "Add input validation to the login function in auth.py",
    "complex": """Implement a new user authentication system with the following requirements:
1. Support for email/password and OAuth login
2. JWT token management with refresh tokens
3. Password reset functionality via email
4. Rate limiting for login attempts
5. Unit tests for all authentication functions
6. Integration with existing user database schema""",
}


def test_initialization():
    """Test AICliInterface initialization"""
    print("=== Testing AICliInterface Initialization ===")

    # Test default initialization
    ai_cli = AICliInterface()
    assert ai_cli.cli_type == "claude"
    assert ai_cli.config["command"] == "claude"
    print("✅ Default initialization works")

    # Test custom CLI type
    ai_cli_custom = AICliInterface("claude")
    assert ai_cli_custom.cli_type == "claude"
    print("✅ Custom CLI type initialization works")

    return True


def test_api_key_detection():
    """Test API key detection"""
    print("\n=== Testing API Key Detection ===")

    ai_cli = AICliInterface()
    api_key = ai_cli.get_api_key()

    if api_key:
        print(f"✅ API key detected: {api_key[:10]}...{api_key[-4:]}")
        return True
    else:
        print("❌ No API key found - set ANTHROPIC_API_KEY environment variable")
        return False


def test_language_config():
    """Test language configuration retrieval"""
    print("\n=== Testing Language Configuration ===")

    ai_cli = AICliInterface()

    # Test Python config
    python_config = ai_cli.get_language_config("python")
    expected_keys = [
        "security_tools",
        "test_command",
        "lint_command",
        "build_command",
        "security_scan",
    ]

    for key in expected_keys:
        if key not in python_config:
            print(f"❌ Missing key in Python config: {key}")
            return False

    print("✅ Python language config complete")

    # Test Rust config
    rust_config = ai_cli.get_language_config("rust")
    for key in expected_keys:
        if key not in rust_config:
            print(f"❌ Missing key in Rust config: {key}")
            return False

    print("✅ Rust language config complete")

    # Test unknown language (should default to Python)
    unknown_config = ai_cli.get_language_config("unknown")
    if unknown_config != python_config:
        print("❌ Unknown language should default to Python config")
        return False

    print("✅ Unknown language defaults to Python config")

    return True


def test_cost_estimation_simple():
    """Test cost estimation with simple task"""
    print("\n=== Testing Cost Estimation (Simple Task) ===")

    ai_cli = AICliInterface()

    if not ai_cli.get_api_key():
        print("❌ Skipping - no API key available")
        return False

    estimate = ai_cli.estimate_task_cost(SAMPLE_TASKS["simple"], "python")

    if not estimate:
        print("❌ Cost estimation returned None")
        return False

    # Check required fields
    required_fields = ["complexity", "estimated_total_cost", "language", "model"]
    for field in required_fields:
        if field not in estimate:
            print(f"❌ Missing required field: {field}")
            return False

    print(f"✅ Simple task estimate: ${estimate['estimated_total_cost']:.4f}")
    print(f"   Complexity: {estimate.get('complexity', 'unknown')}")
    print(f"   Language: {estimate.get('language')}")
    print(f"   Model: {estimate.get('model')}")

    return True


def test_cost_estimation_complex():
    """Test cost estimation with complex task"""
    print("\n=== Testing Cost Estimation (Complex Task) ===")

    ai_cli = AICliInterface()

    if not ai_cli.get_api_key():
        print("❌ Skipping - no API key available")
        return False

    estimate = ai_cli.estimate_task_cost(SAMPLE_TASKS["complex"], "python")

    if not estimate:
        print("❌ Cost estimation returned None")
        return False

    print(f"✅ Complex task estimate: ${estimate['estimated_total_cost']:.4f}")
    print(f"   Complexity: {estimate.get('complexity', 'unknown')}")

    # Complex task should generally cost more than simple
    simple_estimate = ai_cli.estimate_task_cost(SAMPLE_TASKS["simple"], "python")
    if (
        simple_estimate
        and estimate["estimated_total_cost"] > simple_estimate["estimated_total_cost"]
    ):
        print("✅ Complex task costs more than simple task")
    else:
        print("⚠️  Complex task cost not higher than simple (may be okay)")

    return True


def test_cost_estimation_different_languages():
    """Test cost estimation with different programming languages"""
    print("\n=== Testing Cost Estimation (Different Languages) ===")

    ai_cli = AICliInterface()

    if not ai_cli.get_api_key():
        print("❌ Skipping - no API key available")
        return False

    languages = ["python", "rust"]
    estimates = {}

    for lang in languages:
        estimate = ai_cli.estimate_task_cost(SAMPLE_TASKS["medium"], lang)
        if estimate:
            estimates[lang] = estimate
            print(
                f"✅ {lang.title()} estimate: ${estimate['estimated_total_cost']:.4f}"
            )
        else:
            print(f"❌ Failed to get estimate for {lang}")
            return False

    # Both should have valid estimates
    if len(estimates) == len(languages):
        print("✅ All language estimates completed")
        return True

    return False


def test_print_cost_estimate():
    """Test cost estimate printing functionality"""
    print("\n=== Testing Cost Estimate Printing ===")

    ai_cli = AICliInterface()

    # Create a mock estimate
    mock_estimate = {
        "complexity": "medium",
        "estimated_input_tokens": 1500,
        "estimated_output_tokens": 800,
        "estimated_total_cost": 0.0234,
        "cost_factors": ["Code analysis required", "Multiple files to modify"],
        "cost_reduction_tips": ["Be more specific", "Limit scope"],
        "confidence": "high",
        "language": "python",
        "model": "claude-3-5-sonnet",
        "raw_response": "This is a mock response for testing purposes.",
    }

    print("Testing cost estimate printing:")
    ai_cli.print_cost_estimate(mock_estimate, "test task")

    # Test with None estimate
    print("\nTesting None estimate handling:")
    ai_cli.print_cost_estimate(None, "test task")

    print("✅ Cost estimate printing works")
    return True


def test_error_handling():
    """Test error handling with invalid inputs"""
    print("\n=== Testing Error Handling ===")

    ai_cli = AICliInterface()

    if not ai_cli.get_api_key():
        print("❌ Skipping - no API key available")
        return False

    # Test with empty task
    ai_cli.estimate_task_cost("", "python")
    # Should handle gracefully (may return None or low-confidence estimate)
    print("✅ Empty task handled gracefully")

    # Test with very long task
    long_task = "Fix bug " * 1000
    ai_cli.estimate_task_cost(long_task, "python")
    # Should handle gracefully
    print("✅ Long task handled gracefully")

    return True


def main():
    """Run all tests"""
    print("🚀 Testing AI CLI Interface")
    print("=" * 50)

    # Check if API key is available
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  Warning: ANTHROPIC_API_KEY not set. Some tests will be skipped.")

    tests = [
        ("Initialization", test_initialization),
        ("API Key Detection", test_api_key_detection),
        ("Language Configuration", test_language_config),
        ("Cost Estimation (Simple)", test_cost_estimation_simple),
        ("Cost Estimation (Complex)", test_cost_estimation_complex),
        ("Cost Estimation (Languages)", test_cost_estimation_different_languages),
        ("Print Cost Estimate", test_print_cost_estimate),
        ("Error Handling", test_error_handling),
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

    print(f"\n{'=' * 50}")
    print(f"🏁 Results: {passed}/{total} tests passed")
    print(f"{'=' * 50}")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
