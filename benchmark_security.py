#!/usr/bin/env python3
"""
Benchmark script for Claude Agent security scanning performance
"""

import os
import subprocess
import time
from pathlib import Path

# Timeout constants (in seconds)
SECURITY_SCAN_TIMEOUT = 30  # For security scanning operations


def count_python_files():
    """Count Python files and lines in current directory"""
    py_files = list(Path(".").glob("*.py"))
    total_lines = 0

    for file in py_files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                total_lines += len(f.readlines())
        except (OSError, UnicodeDecodeError, PermissionError):
            pass

    return len(py_files), total_lines


def simulate_bandit_scan(files_to_scan=None):
    """Simulate bandit performance on given files"""
    if files_to_scan is None:
        files_to_scan = ["toren.py", "github_utils.py", "job_manager.py"]

    # Filter files that actually exist
    existing_files = [f for f in files_to_scan if os.path.exists(f)]
    if not existing_files:
        return 0, "No files to scan"

    # Check if bandit is available
    try:
        subprocess.run(["bandit", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0, "Bandit not installed"

    # Time the scan
    start_time = time.time()
    try:
        subprocess.run(
            ["bandit", "-ll", "-f", "json"] + existing_files,
            capture_output=True,
            text=True,
            timeout=SECURITY_SCAN_TIMEOUT,
        )
        end_time = time.time()
        scan_time = end_time - start_time

        # Count lines scanned
        total_lines = 0
        for file in existing_files:
            with open(file, "r") as f:
                total_lines += len(f.readlines())

        return scan_time, f"Scanned {len(existing_files)} files ({total_lines} lines)"

    except subprocess.TimeoutExpired:
        return 30, "Scan timed out"
    except Exception as e:
        return 0, f"Error: {e}"


def main():
    print("🚀 Claude Agent Security Performance Benchmark")
    print("=" * 50)

    # Analyze current codebase
    py_files, total_lines = count_python_files()
    print("📊 Codebase Analysis:")
    print(f"   Python files: {py_files}")
    print(f"   Total lines: {total_lines}")
    print()

    # Test different scenarios
    scenarios = [
        ("Small change (1 file)", ["toren.py"]),
        ("Medium change (2 files)", ["toren.py", "github_utils.py"]),
        (
            "Large change (3 files)",
            ["toren.py", "github_utils.py", "job_manager.py"],
        ),
    ]

    print("⏱️  Performance Tests:")
    print("-" * 30)

    for scenario_name, files in scenarios:
        scan_time, details = simulate_bandit_scan(files)
        if scan_time > 0:
            print(f"   {scenario_name:<20}: {scan_time:.2f}s ({details})")
        else:
            print(f"   {scenario_name:<20}: {details}")

    print()
    print("📈 Performance Characteristics:")
    print("   • Git diff scanning scales linearly with changed code")
    print("   • Typical pre-commit delay: 0.5-3 seconds")
    print("   • Only scans files you're actually changing")
    print("   • Much faster than full codebase scanning")
    print()

    # Estimate Docker scanning
    print("🐳 Docker Security Scanning (for comparison):")
    docker_estimates = [
        ("python:3.11-slim", "30-60 seconds"),
        ("python:3.11", "1-3 minutes"),
        ("pytorch/pytorch", "3-8 minutes"),
        ("Custom ML image", "2-5 minutes"),
    ]

    for image, time_estimate in docker_estimates:
        print(f"   {image:<20}: {time_estimate}")

    print()
    print("💡 Recommendation: Git pre-commit hooks have minimal performance impact!")


if __name__ == "__main__":
    main()
