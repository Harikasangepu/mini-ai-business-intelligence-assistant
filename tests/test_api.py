"""Integration tests for FastAPI endpoints (/health and /ask)."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.data_loader import load_csv_to_sqlite
from app.config import settings

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure database is loaded before API tests run."""
    load_csv_to_sqlite(overwrite=True)

@pytest.fixture
def client():
    return TestClient(app)

def test_api_health_endpoint(client):
    """Test GET /health returns 200 and database is healthy."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_connected"] is True
    assert data["total_sales_records"] == 51

def test_api_ask_valid_total_revenue(client):
    """Test POST /ask with Question 1: Total revenue."""
    response = client.post("/ask", json={"question": "What is the total revenue?"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["intent"] == "TOTAL_REVENUE"
    assert data["figures"]["total_revenue"] == 1445200.0
    assert "1,445,200.00" in data["answer"]
    assert "SELECT" in data["sql_query"]

def test_api_ask_valid_highest_product(client):
    """Test POST /ask with Question 2: Highest revenue product."""
    response = client.post("/ask", json={"question": "Which product generated the highest revenue?"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["intent"] == "HIGHEST_REVENUE_PRODUCT"
    assert data["figures"]["top_product"] == "Monitor"
    assert data["figures"]["top_revenue"] == 473000.0

def test_api_ask_valid_monthly_trend(client):
    """Test POST /ask with Question 3: Monthly trend."""
    response = client.post("/ask", json={"question": "What is the monthly revenue trend?"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["intent"] == "MONTHLY_REVENUE_TREND"
    assert "2026-05" in data["figures"]["peak_month"]

def test_api_ask_valid_highest_region(client):
    """Test POST /ask with Question 4: Highest sales region."""
    response = client.post("/ask", json={"question": "Which region generated the highest sales?"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["intent"] == "HIGHEST_SALES_REGION"
    assert data["figures"]["top_region"] == "South"

def test_api_ask_valid_month_comparison_edge_case(client):
    """Test POST /ask with Question 5: Month comparison edge case with natural language."""
    response = client.post("/ask", json={"question": "Compare revenue between April and May"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["intent"] == "REVENUE_CHANGE_BETWEEN_MONTHS"
    assert data["figures"]["month1"] == "2026-04"
    assert data["figures"]["month2"] == "2026-05"
    assert data["figures"]["revenue1"] == 240700.0
    assert data["figures"]["revenue2"] == 318500.0

def test_api_ask_unsupported_question(client):
    """Test POST /ask handles out-of-scope question gracefully without crashing."""
    response = client.post("/ask", json={"question": "What is the capital of France?"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unsupported"
    assert data["intent"] == "UNKNOWN"
    assert "could not map your query" in data["answer"].lower()

def test_api_ask_empty_question_validation(client):
    """Test POST /ask rejects empty or whitespace-only questions."""
    response = client.post("/ask", json={"question": "   "})
    assert response.status_code == 422 or response.status_code == 400
