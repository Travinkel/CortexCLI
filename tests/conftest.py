"""
Pytest Configuration and Fixtures.

This file configures pytest and provides shared fixtures for all tests.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests (require database)")
    config.addinivalue_line("markers", "smoke: Smoke tests for CLI commands")
    config.addinivalue_line("markers", "e2e: End-to-end tests (require API server)")
    config.addinivalue_line("markers", "slow: Slow tests")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location."""
    for item in items:
        # Mark based on test file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "smoke" in str(item.fspath):
            item.add_marker(pytest.mark.smoke)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def db_url():
    """Get database URL from environment or config."""
    import os
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:learning123@localhost:5432/notion_learning_sync"
    )


@pytest.fixture
def sample_atom():
    """Provide a sample atom for testing."""
    return {
        "id": "test-atom-001",
        "front": "What is the OSI model?",
        "back": "A 7-layer reference model for network communication",
        "atom_type": "flashcard",
        "ccna_section_id": "3.5",
    }


@pytest.fixture
def sample_section():
    """Provide a sample CCNA section for testing."""
    return {
        "id": "test-section-001",
        "section_id": "3.5",
        "title": "The OSI Reference Model",
        "module_number": 3,
        "level": 2,
    }


@pytest.fixture
def sample_quiz_question():
    """Provide a sample quiz question for testing."""
    return {
        "id": "test-quiz-001",
        "question": "Which layer of the OSI model handles routing?",
        "answer": "Network Layer (Layer 3)",
        "question_type": "mcq",
        "options": [
            "Physical Layer",
            "Data Link Layer",
            "Network Layer",
            "Transport Layer"
        ],
        "correct_option": 2,
    }
