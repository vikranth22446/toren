#!/bin/bash
set -e

echo "🔗 Installing Git Security Hooks"
echo "================================"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Not in a git repository"
    exit 1
fi

GIT_DIR=$(git rev-parse --git-dir)
HOOKS_DIR="$GIT_DIR/hooks"

# Create pre-commit hook
echo "Installing pre-commit security hook..."
cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
# Security scan pre-commit hook for Toren AI Agent

echo "🔍 Running security scan on changed files..."

# Get script directory relative to git root
SCRIPT_DIR="$(git rev-parse --show-toplevel)/toren"

if [ -f "$SCRIPT_DIR/scripts/scan_diff.sh" ]; then
    cd "$SCRIPT_DIR"
    ./scripts/scan_diff.sh --cached
else
    echo "⚠️  Security scanner not found at $SCRIPT_DIR/scripts/scan_diff.sh"
    echo "Run from toren directory to install hooks properly"
    exit 1
fi
EOF

chmod +x "$HOOKS_DIR/pre-commit"

echo "✅ Pre-commit hook installed"
echo "📋 Security scanning will run automatically before each commit"
echo ""
echo "To skip security check (not recommended):"
echo "  git commit --no-verify"
echo ""
echo "To manually run security scan:"
echo "  ./scripts/scan_diff.sh"