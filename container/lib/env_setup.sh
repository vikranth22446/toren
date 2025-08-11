#!/bin/bash
# Environment and language setup module

setup_language_environment() {
    local language="$1"
    
    echo "🔧 Setting up $language environment..."
    
    case "$language" in
        "rust")
            setup_rust_environment
            ;;
        "python")
            setup_python_environment
            ;;
        "node"|"javascript"|"typescript")
            setup_node_environment
            ;;
        *)
            echo "⚠️  Unknown language: $language, using Python setup"
            setup_python_environment
            ;;
    esac
    
    # Setup documentation workspace
    echo "📁 Setting up documentation workspace..."
    mkdir -p /tmp/claude_docs
    cat > /tmp/claude_docs/README.md << EOF
# Claude Agent Documentation Workspace
This directory is used by AI assistants for scratch work, code analysis, and documentation.
Files here are temporary and used for improving task accuracy and memory management.
EOF
}

setup_rust_environment() {
    echo "🦀 Setting up Rust toolchain..."
    if command -v rustup >/dev/null 2>&1; then
        rustup update 2>/dev/null || echo "Warning: rustup update failed"
        rustup component add clippy rustfmt 2>/dev/null || echo "Warning: rustup components install failed"
    fi
    
    if command -v cargo >/dev/null 2>&1; then
        cargo install --quiet cargo-audit cargo-deny 2>/dev/null || echo "Warning: Rust security tools failed"
    fi
    
    # Create security scan utility
    create_rust_security_scanner
}

setup_python_environment() {
    echo "🐍 Setting up Python toolchain..."
    pip install --quiet bandit safety pip-audit 2>/dev/null || echo "Warning: Python security tools failed"
}

setup_node_environment() {
    echo "📦 Setting up Node.js environment..."
    if command -v npm >/dev/null 2>&1; then
        npm install -g eslint@latest audit-ci 2>/dev/null || echo "Warning: Node security tools failed"
    fi
}

create_rust_security_scanner() {
    cat > /usr/local/bin/rust-security-scan << 'EOF'
#!/bin/bash
echo "🦀 Running Rust security scan..."
cargo audit || echo "Warning: cargo audit failed"
cargo clippy -- -D warnings || echo "Warning: clippy failed" 
cargo deny check 2>/dev/null || echo "Warning: cargo deny failed"
EOF
    chmod +x /usr/local/bin/rust-security-scan
}