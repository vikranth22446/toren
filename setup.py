#!/usr/bin/env python3
"""
Setup script for Toren - Multi-AI CLI Agent Runner
"""

from setuptools import setup

# Read README file
try:
    with open("README_TOREN.md", "r", encoding="utf-8") as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = (
        "Multi-AI CLI Agent Runner - Production-grade autonomous GitHub agent system"
    )

setup(
    name="toren",
    version="1.0.0",
    description="Multi-AI CLI Agent Runner - Production-grade autonomous GitHub agent system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Toren Development Team",
    author_email="dev@toren.ai",
    url="https://github.com/vikranth22446/toren",
    # Include all Python modules in the current directory
    py_modules=[
        "toren",
        "ai_cli_interface",
        "container_manager",
        "input_validator",
        "job_manager",
        "ui_utilities",
        "github_utils",
        "message_templates",
        "cli_parser",
    ],
    # Create the toren command
    entry_points={
        "console_scripts": [
            "toren=toren:main",
        ],
    },
    # Dependencies
    install_requires=[
        "requests>=2.25.0",
    ],
    # Optional dependencies
    extras_require={
        "security": [
            "bandit>=1.7.0",
            "safety>=2.0.0",
        ],
        "dev": [
            "pytest>=6.0.0",
            "flake8>=3.8.0",
        ],
    },
    # Include additional files
    include_package_data=True,
    package_data={
        "": [
            "container/**/*",
            "scripts/**/*",
            "*.json",
            "*.txt",
            "*.md",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Tools",
        "Topic :: System :: Systems Administration",
    ],
    keywords="ai agent github automation docker claude gemini cli toren",
)
