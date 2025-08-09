# Claude Agent Scripts

This directory contains utility scripts for security scanning, performance analysis, and development workflows.

## Security Scripts

### `scan_diff.sh`
**Git diff-based security scanner** - Scans only changed Python files for efficiency
```bash
./scripts/scan_diff.sh                    # Scan working directory changes
./scripts/scan_diff.sh --cached          # Scan staged changes (for pre-commit)
./scripts/scan_diff.sh main              # Scan changes against main branch
```

### `install-hooks.sh` 
**Git pre-commit hook installer** - Sets up automatic security scanning before commits
```bash
./scripts/install-hooks.sh               # Install pre-commit security hooks
```

### `run_security_scan.sh`
**Comprehensive security scanner** - Runs multiple security tools (Bandit, Safety, Semgrep)
```bash
./scripts/run_security_scan.sh           # Full security scan of codebase
```

### `scan_containers.sh`
**Docker security scanner** - Uses Trivy to scan container images for vulnerabilities
```bash
./scripts/scan_containers.sh             # Scan Docker images for CVEs
```

## Analysis Scripts  

### `performance_analysis.sh`
**Performance benchmark tool** - Analyzes security scanning performance characteristics
```bash
./scripts/performance_analysis.sh        # Show performance analysis
```

## Usage Patterns

### Quick Development Workflow
```bash
# 1. Install hooks once
./scripts/install-hooks.sh

# 2. Work normally - security scans run automatically on commit
git add .
git commit -m "Feature: Add new functionality"  # Triggers security scan

# 3. Manual security check when needed
./scripts/scan_diff.sh
```

### Pre-Production Security Check
```bash
# Full security analysis
./scripts/run_security_scan.sh

# Container security scan
./scripts/scan_containers.sh

# Performance analysis
./scripts/performance_analysis.sh
```

## Script Dependencies

| Script | Dependencies | Purpose |
|--------|-------------|---------|
| `scan_diff.sh` | bandit, git | Fast git diff security scanning |
| `install-hooks.sh` | git | Git hook installation |
| `run_security_scan.sh` | bandit, safety, semgrep, jq | Comprehensive security scanning |
| `scan_containers.sh` | trivy, docker | Container vulnerability scanning |
| `performance_analysis.sh` | None | Performance benchmarking |

## Installation

Security tools can be installed with:
```bash
pip install -r ../security-requirements.txt
```

Container scanning requires Trivy:
```bash
# Ubuntu/Debian
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# macOS
brew install trivy
```