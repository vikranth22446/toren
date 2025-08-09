# Installing Toren

## Quick Install

```bash
# Clone the repository
git clone https://github.com/vikranth22446/claude_agent_runner.git
cd claude_agent_runner

# Install with pip (creates 'toren' command)
pip install -e .

# Verify installation
toren --help
```

## Alternative Installation Methods

```bash
# Install from built wheel
python3 setup.py bdist_wheel
pip install dist/toren-1.0.0-py3-none-any.whl

# Direct setup.py install
python3 setup.py install
```

## Prerequisites

- **Python 3.8+**
- **Docker** (for container execution)
- **pip** (Python package installer)

## Usage After Installation

```bash
# The 'toren' command is now available system-wide
toren --help
toren run --help
toren status

# Examples
toren run --cli-type claude --base-image python:3.11 --spec task.md --branch fix/bug
toren run --cli-type gemini --base-image python:3.11 --spec task.md --branch fix/bug
```

## Configuration

Set up your AI CLI credentials:

**For Claude:**
```bash
# Option 1: Install Claude CLI and configure
curl -fsSL https://claude.ai/install.sh | bash

# Option 2: Set environment variable
export ANTHROPIC_API_KEY=your_key_here
```

**For Gemini:**
```bash
# Install Gemini CLI
npm install -g @google/generative-ai-cli

# Set environment variable
export GEMINI_API_KEY=your_key_here
```

**For GitHub:**
```bash
export GITHUB_TOKEN=your_github_token
```

## Uninstall

```bash
pip uninstall toren
```

That's it! No shell scripts, no manual setup - just standard Python packaging.