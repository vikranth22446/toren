#!/usr/bin/env python3
"""
AI CLI Execution Utilities - Helper functions for AI CLI operations
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class AICliExecUtils:
    """Utilities for AI CLI execution operations"""

    def __init__(self):
        self.cwd = Path.cwd()

    def detect_project_language(self) -> Tuple[str, List[str]]:
        """
        Detect the primary language and package files in the project
        Returns: (language, package_files)
        """
        language_indicators = {
            'python': ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile', '*.py'],
            'node': ['package.json', 'package-lock.json', 'yarn.lock', '*.js', '*.ts'],
            'rust': ['Cargo.toml', 'Cargo.lock', '*.rs'],
            'go': ['go.mod', 'go.sum', '*.go'],
            'java': ['pom.xml', 'build.gradle', '*.java'],
            'ruby': ['Gemfile', 'Gemfile.lock', '*.rb'],
        }
        
        detected_languages = {}
        package_files = []
        
        for lang, indicators in language_indicators.items():
            score = 0
            lang_files = []
            
            for indicator in indicators:
                if indicator.startswith('*.'):
                    # Count source files
                    ext = indicator[1:]
                    count = len(list(self.cwd.rglob(f'*{ext}')))
                    score += count
                else:
                    # Check for package files
                    if (self.cwd / indicator).exists():
                        score += 10
                        lang_files.append(indicator)
            
            if score > 0:
                detected_languages[lang] = score
                package_files.extend(lang_files)
        
        if not detected_languages:
            return 'generic', []
        
        primary_language = max(detected_languages, key=detected_languages.get)
        return primary_language, package_files

    def get_base_image_for_language(self, language: str) -> str:
        """Get the appropriate base image for a detected language"""
        base_images = {
            'python': 'python:3.11-slim',
            'node': 'node:18-alpine',
            'rust': 'rust:1.70-slim',
            'go': 'golang:1.20-alpine',
            'java': 'openjdk:17-jdk-slim',
            'ruby': 'ruby:3.1-slim',
            'generic': 'ubuntu:22.04'
        }
        return base_images.get(language, 'ubuntu:22.04')

    def get_system_dependencies(self, language: str) -> List[str]:
        """Get system dependencies needed for the language"""
        dependencies = {
            'python': ['git', 'curl', 'build-essential'],
            'node': ['git', 'curl'],
            'rust': ['git', 'curl', 'build-essential'],
            'go': ['git', 'curl'],
            'java': ['git', 'curl'],
            'ruby': ['git', 'curl', 'build-essential'],
            'generic': ['git', 'curl', 'build-essential']
        }
        return dependencies.get(language, ['git', 'curl', 'build-essential'])

    def get_package_install_commands(self, language: str, package_files: List[str]) -> List[str]:
        """Generate package installation commands based on detected files"""
        commands = []
        
        if language == 'python':
            if 'requirements.txt' in package_files:
                commands.append('RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi')
            if 'setup.py' in package_files:
                commands.append('RUN if [ -f setup.py ]; then pip install -e .; fi')
            if 'pyproject.toml' in package_files:
                commands.append('RUN if [ -f pyproject.toml ]; then pip install -e .; fi')
        
        elif language == 'node':
            if 'package.json' in package_files:
                commands.append('RUN if [ -f package.json ]; then npm ci --only=production; fi')
        
        elif language == 'rust':
            if 'Cargo.toml' in package_files:
                commands.append('RUN if [ -f Cargo.toml ]; then cargo build --release; fi')
        
        elif language == 'go':
            if 'go.mod' in package_files:
                commands.append('RUN if [ -f go.mod ]; then go mod download; fi')
                commands.append('RUN if [ -f go.mod ]; then go build -o app .; fi')
        
        elif language == 'java':
            if 'pom.xml' in package_files:
                commands.append('RUN if [ -f pom.xml ]; then ./mvnw clean package -DskipTests; fi')
            elif 'build.gradle' in package_files:
                commands.append('RUN if [ -f build.gradle ]; then ./gradlew build -x test; fi')
        
        elif language == 'ruby':
            if 'Gemfile' in package_files:
                commands.append('RUN if [ -f Gemfile ]; then bundle install --deployment --without development test; fi')
        
        return commands

    def analyze_project_size(self) -> Dict[str, int]:
        """Analyze project to optimize Docker image size"""
        try:
            # Count various file types to understand project structure
            source_files = len(list(self.cwd.rglob('*.py'))) + len(list(self.cwd.rglob('*.js'))) + \
                          len(list(self.cwd.rglob('*.ts'))) + len(list(self.cwd.rglob('*.rs'))) + \
                          len(list(self.cwd.rglob('*.go'))) + len(list(self.cwd.rglob('*.java')))
            
            config_files = len(list(self.cwd.rglob('*.json'))) + len(list(self.cwd.rglob('*.yml'))) + \
                          len(list(self.cwd.rglob('*.yaml'))) + len(list(self.cwd.rglob('*.toml')))
            
            return {
                'source_files': source_files,
                'config_files': config_files,
                'is_large': source_files > 100
            }
        except Exception:
            return {'source_files': 0, 'config_files': 0, 'is_large': False}

    def generate_dockerfile_content(self, base_image: Optional[str] = None) -> str:
        """Generate optimized Dockerfile content based on codebase analysis"""
        language, package_files = self.detect_project_language()
        
        if not base_image:
            base_image = self.get_base_image_for_language(language)
        
        system_deps = self.get_system_dependencies(language)
        package_commands = self.get_package_install_commands(language, package_files)
        project_analysis = self.analyze_project_size()
        
        dockerfile_lines = [
            f"# Dockerfile for {language.title()} project",
            f"FROM {base_image}",
            "",
            "# Install system dependencies"
        ]
        
        if system_deps:
            if base_image.endswith('-alpine'):
                dockerfile_lines.append(f"RUN apk add --no-cache {' '.join(system_deps)}")
            else:
                deps_line = ' \\\n    '.join(system_deps)
                dockerfile_lines.extend([
                    "RUN apt-get update && apt-get install -y \\",
                    f"    {deps_line} \\",
                    "    && rm -rf /var/lib/apt/lists/*"
                ])
        
        dockerfile_lines.extend([
            "",
            "# Set working directory",
            "WORKDIR /workspace",
            ""
        ])
        
        # Optimize for build caching by copying dependency files first
        if package_files:
            dockerfile_lines.append("# Copy dependency files first for better caching")
            for package_file in package_files:
                dockerfile_lines.append(f"COPY {package_file} /workspace/")
            dockerfile_lines.append("")
            
            # Add package installation commands
            if package_commands:
                dockerfile_lines.append("# Install dependencies")
                dockerfile_lines.extend(package_commands)
                dockerfile_lines.append("")
        
        dockerfile_lines.extend([
            "# Copy project files",
            "COPY . /workspace/",
            ""
        ])
        
        # Add optimizations for large projects
        if project_analysis['is_large']:
            dockerfile_lines.extend([
                "# Optimize for large projects",
                "RUN find /workspace -name '__pycache__' -type d -exec rm -rf {} + || true",
                "RUN find /workspace -name '*.pyc' -delete || true",
                "RUN find /workspace -name '.git' -type d -exec rm -rf {} + || true",
                ""
            ])
        
        # Add default command
        dockerfile_lines.extend([
            "# Default command",
            'CMD ["/bin/bash"]'
        ])
        
        return '\n'.join(dockerfile_lines) + '\n'

    def write_dockerfile(self, base_image: Optional[str] = None) -> bool:
        """
        Generate and write Dockerfile to current working directory
        Returns: True if successful, False otherwise
        """
        try:
            dockerfile_path = self.cwd / "Dockerfile"
            
            # Check if Dockerfile already exists
            if dockerfile_path.exists():
                print(f"⚠️  Dockerfile already exists at {dockerfile_path}")
                response = input("Do you want to overwrite it? (y/N): ").strip().lower()
                if response not in ['y', 'yes']:
                    print("❌ Dockerfile generation cancelled")
                    return False
            
            # Generate content
            content = self.generate_dockerfile_content(base_image)
            
            # Write to file
            with open(dockerfile_path, 'w') as f:
                f.write(content)
            
            print(f"✅ Successfully generated Dockerfile at {dockerfile_path}")
            
            # Show summary
            language, package_files = self.detect_project_language()
            print(f"📊 Project analysis:")
            print(f"   Language: {language}")
            print(f"   Base image: {base_image or self.get_base_image_for_language(language)}")
            if package_files:
                print(f"   Package files: {', '.join(package_files)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error generating Dockerfile: {e}")
            return False