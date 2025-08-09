#!/bin/bash
echo "🕐 Claude Agent Security Scanning Performance Analysis"
echo "====================================================="

echo
echo "📊 Git Pre-commit Hook Performance:"
echo "-----------------------------------"

# Count Python files and lines in current repo
if [ -d ".git" ]; then
    echo "Repository analysis:"
    
    # Total Python files
    PY_FILES=$(find . -name "*.py" -not -path "./.venv/*" -not -path "./venv/*" | wc -l)
    echo "  Total Python files: $PY_FILES"
    
    # Total lines of Python code
    TOTAL_LINES=$(find . -name "*.py" -not -path "./.venv/*" -not -path "./venv/*" -exec wc -l {} + 2>/dev/null | tail -n 1 | awk '{print $1}' || echo "0")
    echo "  Total Python lines: $TOTAL_LINES"
    
    # Simulate typical change sizes
    echo
    echo "Typical git diff scenarios:"
    echo "  • 1-2 files changed (small fix): ~50-200 lines → Bandit scan: 0.5-1 seconds"
    echo "  • 3-5 files changed (feature): ~200-500 lines → Bandit scan: 1-2 seconds" 
    echo "  • 5+ files changed (major): ~500+ lines → Bandit scan: 2-3 seconds"
    
    # Test with actual files if bandit is available
    if command -v bandit &> /dev/null; then
        echo
        echo "🔍 Real performance test with current codebase:"
        
        # Time bandit on main files
        MAIN_FILES="toren.py github_utils.py job_manager.py"
        if ls $MAIN_FILES >/dev/null 2>&1; then
            echo "  Testing bandit on main files..."
            BANDIT_TIME=$( (time bandit -ll -f json $MAIN_FILES >/dev/null 2>&1) 2>&1 | grep real | awk '{print $2}')
            echo "  ✅ Bandit scan completed in: $BANDIT_TIME"
        else
            echo "  ⏭️  Main files not found, skipping real test"
        fi
    else
        echo
        echo "  💡 Install bandit to see real performance: pip install bandit"
    fi
else
    echo "  ⚠️  Not in a git repository"
fi

echo
echo "🐳 Docker Security Scanning Performance:"
echo "---------------------------------------"
echo "Docker security scans are much slower because they:"
echo "  • Download/analyze entire container images (100MB - 2GB+)"
echo "  • Check against CVE databases"
echo "  • Scan all OS packages and dependencies"
echo
echo "Typical Docker scan times:"
echo "  • python:3.11-slim (~45MB): 30-60 seconds"
echo "  • python:3.11 (~300MB): 1-3 minutes"
echo "  • pytorch/pytorch:latest (~4GB): 3-8 minutes"
echo "  • Custom project images: 1-5 minutes"
echo
echo "💡 This is why --security flag is optional for health checks!"

echo
echo "📋 Performance Summary:"
echo "======================"
echo "Git pre-commit hooks: ⚡ Very fast (0.5-3 seconds)"
echo "  • Only scans changed files"
echo "  • Linear with amount of changed code"
echo "  • Minimal impact on developer workflow"
echo
echo "Docker security scans: 🐌 Slow (30 seconds - 8 minutes)"
echo "  • Scans entire container image"
echo "  • Good for CI/CD and production validation"
echo "  • Use --security flag only when needed"

echo
echo "🚀 Recommendations:"
echo "==================="
echo "• Enable git pre-commit hooks (minimal overhead)"
echo "• Use --security flag for:"
echo "  - Production deployments"
echo "  - New base image validation"
echo "  - Weekly/monthly security reviews"
echo "• Skip --security flag for:"
echo "  - Daily development"
echo "  - Quick health checks"
echo "  - CI builds (unless specifically needed)"