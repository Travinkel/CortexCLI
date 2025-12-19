"""
Setup script for cortex-cli (formerly notion-learning-sync).

Cortex CLI is the terminal-based learning companion for the
Right Learning ecosystem. It serves three roles:

1. Developer's Companion - Quick study sessions from the terminal
2. Content Pipeline - CI/CD validation for learning content
3. Offline Fallback - Air-gapped study with later sync

The 'cortex' command is the primary entry point, while 'nls'
is maintained for backwards compatibility.
"""

from setuptools import find_packages, setup

setup(
    name="cortex-cli",
    version="2.0.0",
    description="Terminal-based cognitive learning companion - part of Right Learning",
    long_description=open("README.md", encoding="utf-8").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="Right Learning",
    url="https://github.com/rightlearning/cortex-cli",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        # CLI
        "typer>=0.9.0",
        "rich>=13.0.0",
        # Database
        "sqlalchemy>=2.0.0",
        "psycopg2-binary>=2.9.0",
        # Config & Validation
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        # HTTP
        "httpx>=0.25.0",
        "requests>=2.28.0",
        # Logging
        "loguru>=0.7.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "ruff>=0.1.0",
            "mypy>=1.0.0",
        ],
        "local-ai": [
            "ollama>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            # Primary entry point
            "cortex=src.cli.cortex_cli:run",
            # Legacy entry point (backwards compatibility)
            "nls=src.cli.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Education",
        "Topic :: Education :: Computer Aided Instruction (CAI)",
    ],
    keywords="learning spaced-repetition cli education cognitive",
)
