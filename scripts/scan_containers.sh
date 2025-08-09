#!/bin/bash
set -e

echo "🐳 Docker Security Scanning"
echo "==========================="

# Install Trivy if not present
if ! command -v trivy &> /dev/null; then
    echo "Installing Trivy container scanner..."
    # For Ubuntu/Debian
    if command -v conda &> /dev/null; then
        conda install -y -c conda-forge trivy
    elif command -v apt &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y wget apt-transport-https gnupg lsb-release
        wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
        echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
        sudo apt-get update
        sudo apt-get install -y trivy
    # For macOS
    elif command -v brew &> /dev/null; then
        brew install trivy
    else
        echo "Please install Trivy manually: https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
        exit 1
    fi
fi

echo "🔍 Scanning Dockerfile for vulnerabilities..."
if [ -f "Dockerfile" ]; then
    trivy config --format json --output dockerfile-scan.json Dockerfile || true
    trivy config Dockerfile
else
    echo "No Dockerfile found in current directory"
fi

echo
echo "🖼️  Scanning common base images..."
echo "Scanning python:3.11 (common base image):"
trivy image --format json --output python-base-scan.json python:3.11 || true
trivy image --severity HIGH,CRITICAL python:3.11

echo
echo "🖼️  Scanning pytorch/pytorch:latest (ML base image):"
trivy image --format json --output pytorch-base-scan.json pytorch/pytorch:latest || true
trivy image --severity HIGH,CRITICAL pytorch/pytorch:latest

# Scan any locally built Claude Agent images
echo
echo "🖼️  Scanning locally built Claude Agent images..."
for image in $(docker images --format "{{.Repository}}:{{.Tag}}" | grep claude-agent || true); do
    echo "Scanning $image:"
    trivy image --format json --output "${image//\//-}-scan.json" "$image" || true
    trivy image --severity HIGH,CRITICAL "$image"
done

echo
echo "📋 Container Security Reports Generated:"
echo "========================================"
ls -la *-scan.json 2>/dev/null || echo "No scan reports generated"