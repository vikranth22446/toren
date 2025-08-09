#!/usr/bin/env python3
"""
Manual Test Script for github_utils.py - Real GitHub API calls with user verification

Usage:
1. Update TEST_ISSUE_NUMBER and TEST_PR_NUMBER below
2. Run: python3 tests/test_github_utils.py
3. Check GitHub and confirm each operation worked with y/n prompts
"""

from github_utils import GitHubUtils
import sys
from pathlib import Path

# Add parent directory to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))


# UPDATE THESE FOR YOUR TEST REPO
TEST_ISSUE_NUMBER = "1"
TEST_PR_NUMBER = "2"


def confirm(message):
    """Ask user to confirm if operation worked"""
    response = input(f"{message} (y/n): ").strip().lower()
    return response == "y"


def test_get_issue():
    """Test getting issue data"""
    print("\n=== Testing get_issue ===")
    utils = GitHubUtils()

    issue = utils.get_issue(TEST_ISSUE_NUMBER)
    if issue:
        print(f"Retrieved issue: {issue['title']}")
        return confirm("Did this show the correct issue data?")
    else:
        print("Failed to get issue")
        return False


def test_comment_issue():
    """Test commenting on issue"""
    print("\n=== Testing comment_issue ===")
    utils = GitHubUtils()

    message = "🤖 Test comment - please ignore"
    success = utils.comment_issue(TEST_ISSUE_NUMBER, message)

    if success:
        print(f"Posted comment to issue #{TEST_ISSUE_NUMBER}")
        return confirm(f"Check issue #{TEST_ISSUE_NUMBER} - did the comment appear?")
    return False


def test_get_pr():
    """Test getting PR data"""
    print("\n=== Testing get_pr ===")
    utils = GitHubUtils()

    pr = utils.get_pr(TEST_PR_NUMBER)
    if pr:
        print(f"Retrieved PR: {pr['title']}")
        return confirm("Did this show the correct PR data?")
    else:
        print("Failed to get PR")
        return False


def test_comment_pr():
    """Test commenting on PR"""
    print("\n=== Testing comment_pr ===")
    utils = GitHubUtils()

    message = "🤖 Test PR comment - please ignore"
    success = utils.comment_pr(TEST_PR_NUMBER, message)

    if success:
        print(f"Posted comment to PR #{TEST_PR_NUMBER}")
        return confirm(f"Check PR #{TEST_PR_NUMBER} - did the comment appear?")
    return False


def test_notifications():
    """Test notification methods"""
    print("\n=== Testing notifications ===")
    utils = GitHubUtils()

    # Test progress notification
    success = utils.notify_progress("Testing", "Manual test", TEST_ISSUE_NUMBER)
    if not success:
        return False

    if not confirm(
        f"Check issue #{TEST_ISSUE_NUMBER} - did progress notification appear?"
    ):
        return False

    # Test completion notification
    success = utils.notify_completion("Test completed", issue_number=TEST_ISSUE_NUMBER)
    if not success:
        return False

    return confirm(
        f"Check issue #{TEST_ISSUE_NUMBER} - did completion notification appear?"
    )


def main():
    print("🚀 Manual GitHub Utils Test")
    print(f"Testing with Issue #{TEST_ISSUE_NUMBER} and PR #{TEST_PR_NUMBER}")

    tests = [
        ("Get Issue", test_get_issue),
        ("Comment Issue", test_comment_issue),
        ("Get PR", test_get_pr),
        ("Comment PR", test_comment_pr),
        ("Notifications", test_notifications),
    ]

    passed = 0
    for name, test_func in tests:
        try:
            if test_func():
                print(f"✅ {name} PASSED")
                passed += 1
            else:
                print(f"❌ {name} FAILED")
        except Exception as e:
            print(f"❌ {name} ERROR: {e}")

    print(f"\n🏁 Results: {passed}/{len(tests)} tests passed")


if __name__ == "__main__":
    main()
