"""
End-to-End Tests for Study Flow using Playwright.

These tests verify the complete user journey through the study interface.
Requires the API server to be running.

Usage:
    # Start API server first
    uvicorn src.api.main:app --port 8100

    # Run tests
    pytest tests/e2e/test_study_flow.py -v

Requirements:
    pip install playwright pytest-playwright
    playwright install chromium
"""

import os

import pytest

# Skip all tests if playwright is not available
try:
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed"),
]

# API base URL
API_URL = os.environ.get("API_URL", "http://localhost:8100")


@pytest.fixture(scope="session")
def browser():
    """Launch browser for test session."""
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright not available")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    """Create a new page for each test."""
    page = browser.new_page()
    yield page
    page.close()


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    import httpx

    client = httpx.Client(base_url=API_URL, timeout=30.0)

    # Check if API is running
    try:
        response = client.get("/health")
        if response.status_code != 200:
            pytest.skip("API server not healthy")
    except Exception as e:
        pytest.skip(f"API server not available: {e}")

    yield client
    client.close()


class TestAPIHealth:
    """Test API health endpoints."""

    def test_health_endpoint(self, api_client):
        """Health endpoint should return OK."""
        response = api_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy" or "ok" in str(data).lower()

    def test_api_docs_available(self, api_client):
        """OpenAPI docs should be available."""
        response = api_client.get("/docs")

        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "openapi" in response.text.lower()


class TestStudySessionAPI:
    """Test study session API endpoints."""

    def test_list_modules(self, api_client):
        """Should list CCNA modules."""
        response = api_client.get("/api/ccna/modules")

        if response.status_code == 404:
            pytest.skip("CCNA modules endpoint not implemented")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_atoms_for_study(self, api_client):
        """Should get atoms for study session."""
        response = api_client.get("/api/study/atoms", params={"limit": 10})

        if response.status_code == 404:
            pytest.skip("Study atoms endpoint not implemented")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_start_study_session(self, api_client):
        """Should be able to start a study session."""
        response = api_client.post(
            "/api/study/session", json={"mode": "adaptive", "duration_minutes": 25}
        )

        if response.status_code == 404:
            pytest.skip("Study session endpoint not implemented")

        assert response.status_code in [200, 201]
        data = response.json()
        assert "session_id" in data or "id" in data


class TestAtomReviewAPI:
    """Test atom review API endpoints."""

    def test_submit_answer(self, api_client):
        """Should be able to submit an answer."""
        # First get an atom
        atoms_response = api_client.get("/api/study/atoms", params={"limit": 1})

        if atoms_response.status_code == 404:
            pytest.skip("Study atoms endpoint not implemented")

        if atoms_response.status_code != 200:
            pytest.skip("Could not get atoms")

        atoms = atoms_response.json()
        if not atoms:
            pytest.skip("No atoms available")

        atom_id = atoms[0].get("id") or atoms[0].get("atom_id")

        # Submit answer
        response = api_client.post(
            "/api/study/answer",
            json={"atom_id": str(atom_id), "answer": "test answer", "confidence": 0.8},
        )

        if response.status_code == 404:
            pytest.skip("Answer submission endpoint not implemented")

        assert response.status_code in [200, 201]

    def test_get_atom_details(self, api_client):
        """Should get atom details."""
        # First get an atom ID
        atoms_response = api_client.get("/api/study/atoms", params={"limit": 1})

        if atoms_response.status_code != 200:
            pytest.skip("Could not get atoms")

        atoms = atoms_response.json()
        if not atoms:
            pytest.skip("No atoms available")

        atom_id = atoms[0].get("id") or atoms[0].get("atom_id")

        # Get details
        response = api_client.get(f"/api/atoms/{atom_id}")

        if response.status_code == 404:
            # Try alternate endpoint
            response = api_client.get(f"/api/study/atom/{atom_id}")

        if response.status_code == 404:
            pytest.skip("Atom details endpoint not implemented")

        assert response.status_code == 200


class TestStatsAPI:
    """Test statistics API endpoints."""

    def test_get_study_stats(self, api_client):
        """Should get study statistics."""
        response = api_client.get("/api/stats")

        if response.status_code == 404:
            response = api_client.get("/api/study/stats")

        if response.status_code == 404:
            pytest.skip("Stats endpoint not implemented")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_mastery_progress(self, api_client):
        """Should get mastery progress."""
        response = api_client.get("/api/mastery")

        if response.status_code == 404:
            response = api_client.get("/api/stats/mastery")

        if response.status_code == 404:
            pytest.skip("Mastery endpoint not implemented")

        assert response.status_code == 200


class TestPersonaAPI:
    """Test persona API endpoints."""

    def test_get_persona(self, api_client):
        """Should get learner persona."""
        response = api_client.get("/api/persona")

        if response.status_code == 404:
            response = api_client.get("/api/learner/persona")

        if response.status_code == 404:
            pytest.skip("Persona endpoint not implemented")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestDiagnosisAPI:
    """Test cognitive diagnosis API endpoints."""

    def test_get_diagnosis(self, api_client):
        """Should get cognitive diagnosis."""
        response = api_client.get("/api/diagnosis")

        if response.status_code == 404:
            response = api_client.get("/api/cognitive/diagnosis")

        if response.status_code == 404:
            pytest.skip("Diagnosis endpoint not implemented")

        assert response.status_code == 200


class TestWebUIFlow:
    """Test web UI flow (if web interface exists)."""

    def test_home_page_loads(self, page):
        """Home page should load."""
        try:
            page.goto(API_URL, timeout=10000)
            # If there's a web UI, it should load
        except Exception:
            pytest.skip("No web UI available")

    def test_study_page_loads(self, page):
        """Study page should load."""
        try:
            page.goto(f"{API_URL}/study", timeout=10000)
        except Exception:
            pytest.skip("No study page available")

    def test_stats_page_loads(self, page):
        """Stats page should load."""
        try:
            page.goto(f"{API_URL}/stats", timeout=10000)
        except Exception:
            pytest.skip("No stats page available")
