"""Setup script for notion-learning-sync."""
from setuptools import setup, find_packages

setup(
    name="notion-learning-sync",
    version="0.1.0",
    description="CCNA Learning Path CLI with Anki sync",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "typer>=0.9.0",
        "rich>=13.0.0",
        "sqlalchemy>=2.0.0",
        "psycopg2-binary>=2.9.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "requests>=2.28.0",
        "loguru>=0.7.0",
    ],
    entry_points={
        "console_scripts": [
            "nls=src.cli.main:main",
        ],
    },
)
