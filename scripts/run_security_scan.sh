#!/bin/bash
set -e

echo "🔍 Running Security Scans for Claude Agent..."

# Install security tools if not present
if ! command -v bandit &> /dev/null; then
    echo "Installing security scanning tools..."
    pip install -r security-requirements.txt
fi

echo "📊 1. Python Code Security Scan (Bandit)"
echo "======================================"
bandit -r . -f json -o bandit-report.json || true
bandit -r . -ll  # Show only high/medium severity

echo
echo "🛡️  2. Dependency Vulnerability Scan (Safety)"
echo "=============================================="
safety check --json --output safety-report.json || true
safety check --short-report

echo
echo "🔎 3. Package Vulnerability Scan (pip-audit)"
echo "============================================="
pip-audit --format=json --output=pip-audit-report.json . || true
pip-audit --desc

echo
echo "⚡ 4. Advanced Static Analysis (Semgrep)"
echo "========================================"
semgrep --config=auto --json --output=semgrep-report.json . || true
semgrep --config=auto --severity=ERROR --severity=WARNING .

echo
echo "📋 Security Scan Summary:"
echo "========================="
echo "Reports generated:"
echo "  - bandit-report.json"
echo "  - safety-report.json" 
echo "  - pip-audit-report.json"
echo "  - semgrep-report.json"

# Check for critical issues
critical_issues=0

if [ -f bandit-report.json ]; then
    high_severity=$(jq '.results[] | select(.issue_severity=="HIGH")' bandit-report.json | wc -l)
    if [ "$high_severity" -gt 0 ]; then
        echo "⚠️  Found $high_severity high-severity Bandit issues"
        critical_issues=$((critical_issues + 1))
    fi
fi

if [ -f safety-report.json ]; then
    vulnerabilities=$(jq '.vulnerabilities | length' safety-report.json 2>/dev/null || echo "0")
    if [ "$vulnerabilities" -gt 0 ]; then
        echo "⚠️  Found $vulnerabilities dependency vulnerabilities"
        critical_issues=$((critical_issues + 1))
    fi
fi

if [ "$critical_issues" -gt 0 ]; then
    echo "❌ Security scan found critical issues!"
    exit 1
else
    echo "✅ Security scan completed - no critical issues found"
fi