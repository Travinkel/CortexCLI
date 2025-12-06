"""
Pytest configuration for BDD tests.

This module provides shared fixtures and configuration for the
pytest-bdd behavior-driven tests of the Cortex neuromorphic architecture.
"""

import sys
from pathlib import Path

import pytest

# Ensure src is in the path
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture(autouse=True)
def setup_logging():
    """Configure logging for BDD tests."""
    from loguru import logger
    import sys

    # Remove default handler
    logger.remove()

    # Add test handler
    logger.add(
        sys.stderr,
        level="DEBUG",
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    yield

    # Cleanup
    logger.remove()


def pytest_bdd_apply_tag(tag, function):
    """
    Apply pytest markers based on Gherkin tags.

    Tags in the feature file become pytest markers:
    - @hippocampus -> pytest.mark.hippocampus
    - @critical -> pytest.mark.critical
    - @slow -> pytest.mark.slow
    """
    marker = getattr(pytest.mark, tag)
    return marker(function)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "hippocampus: Tests for hippocampal pattern separation"
    )
    config.addinivalue_line(
        "markers", "pattern_separation: Tests for pattern separation (DG)"
    )
    config.addinivalue_line(
        "markers", "pfit: Tests for P-FIT integration"
    )
    config.addinivalue_line(
        "markers", "integration: Tests for integration (P-FIT)"
    )
    config.addinivalue_line(
        "markers", "pfc: Tests for prefrontal cortex function"
    )
    config.addinivalue_line(
        "markers", "executive_function: Tests for executive function"
    )
    config.addinivalue_line(
        "markers", "fatigue: Tests for fatigue detection"
    )
    config.addinivalue_line(
        "markers", "success: Tests for success classification"
    )
    config.addinivalue_line(
        "markers", "fluency: Tests for fluency detection"
    )
    config.addinivalue_line(
        "markers", "cognitive_load: Tests for cognitive load"
    )
    config.addinivalue_line(
        "markers", "plm: Tests for Perceptual Learning Module"
    )
    config.addinivalue_line(
        "markers", "force_z: Tests for Force Z backtracking"
    )
    config.addinivalue_line(
        "markers", "prerequisites: Tests for prerequisite checking"
    )
    config.addinivalue_line(
        "markers", "struggle: Tests for struggle detection"
    )
    config.addinivalue_line(
        "markers", "hrl: Tests for Hierarchical RL"
    )
    config.addinivalue_line(
        "markers", "reward: Tests for reward computation"
    )
    config.addinivalue_line(
        "markers", "critical: Critical path tests"
    )
    config.addinivalue_line(
        "markers", "encoding: Tests for encoding errors"
    )
    config.addinivalue_line(
        "markers", "retrieval: Tests for retrieval errors"
    )
    config.addinivalue_line(
        "markers", "procedural: Tests for procedural atoms"
    )
    config.addinivalue_line(
        "markers", "session: Tests for session-level behaviors"
    )
    config.addinivalue_line(
        "markers", "fluency_training: Tests for PLM fluency training"
    )
    config.addinivalue_line(
        "markers", "achieved: Tests for fluency achieved state"
    )
    config.addinivalue_line(
        "markers", "penalty: Tests for penalty calculations"
    )
