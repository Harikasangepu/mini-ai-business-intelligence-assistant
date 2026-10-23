"""Unit tests for query execution service and SQL safety validator."""
import pytest
from pathlib import Path
from app.data_loader import load_csv_to_sqlite
from app.query_service import (
    validate_sql_safety,
    execute_safe_query,
    query_total_revenue,
    query_highest_revenue_product,
    query_monthly_revenue_trend,
    query_highest_sales_region,
    query_revenue_change_between_months
)

@pytest.fixture(scope="module")
def setup_test_db(tmp_path_factory):
    """Fixture to ensure temporary SQLite database is loaded with test data."""
    db_dir = tmp_path_factory.mktemp("db")
    test_db = db_dir / "test_sales.db"
    load_csv_to_sqlite(db_path=test_db, overwrite=True)
    return test_db

def test_sql_safety_validator():
    """Verify that destructive operations are blocked and read-only queries are permitted."""
    # Permitted queries
    safe_queries = [
        "SELECT * FROM sales LIMIT 5;",
        "SELECT product, SUM(line_revenue) FROM sales GROUP BY product",
        "WITH monthly AS (SELECT strftime('%Y-%m', order_date) AS m FROM sales) SELECT * FROM monthly;"
    ]
    for q in safe_queries:
        is_safe, err = validate_sql_safety(q)
        assert is_safe, f"Safe query was flagged as unsafe: {q} (Error: {err})"
        
    # Blocked queries (destructive / injection)
    unsafe_queries = [
        "DROP TABLE sales;",
        "DELETE FROM sales WHERE quantity = 0;",
        "UPDATE sales SET line_revenue = 0;",
        "INSERT INTO sales VALUES ('TXN9999', '2026-01-01', 'Test', 'Cat', 'North', 'Online', 1, 10, 0, 'Completed', 10, 0);",
        "ALTER TABLE sales ADD COLUMN hack TEXT;",
        "SELECT 1; DROP TABLE sales;",
        "PRAGMA table_info(sales);",
        ""
    ]
    for q in unsafe_queries:
        is_safe, err = validate_sql_safety(q)
        assert not is_safe, f"Unsafe query was incorrectly permitted: {q}"

def test_query_total_revenue(setup_test_db):
    """Test Question 1: What is the total revenue?"""
    res = query_total_revenue(db_path=setup_test_db)
    assert res["intent"] == "TOTAL_REVENUE"
    assert res["figures"]["total_revenue"] == 1445200.0
    assert res["figures"]["completed_transactions"] == 49
    assert res["figures"]["total_units_sold"] == 638
    assert "1,445,200.00" in res["answer"]
    assert "SELECT" in res["sql_query"]

def test_query_highest_revenue_product(setup_test_db):
    """Test Question 2: Which product generated the highest revenue?"""
    res = query_highest_revenue_product(db_path=setup_test_db)
    assert res["intent"] == "HIGHEST_REVENUE_PRODUCT"
    assert res["figures"]["top_product"] == "Monitor"
    assert res["figures"]["top_revenue"] == 473000.0
    assert res["figures"]["top_units_sold"] == 50
    assert "Monitor" in res["answer"]

def test_query_monthly_revenue_trend(setup_test_db):
    """Test Question 3: What is the monthly revenue trend?"""
    res = query_monthly_revenue_trend(db_path=setup_test_db)
    assert res["intent"] == "MONTHLY_REVENUE_TREND"
    months = res["figures"]["months"]
    assert months == ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
    assert res["figures"]["peak_month"] == "2026-05"
    assert res["figures"]["peak_revenue"] == 318500.0

def test_query_highest_sales_region(setup_test_db):
    """Test Question 4: Which region generated the highest sales?"""
    res = query_highest_sales_region(db_path=setup_test_db)
    assert res["intent"] == "HIGHEST_SALES_REGION"
    assert res["figures"]["top_region"] == "South"
    assert res["figures"]["top_revenue"] == 411200.0
    assert res["figures"]["top_units_sold"] == 182

def test_query_revenue_change_between_months(setup_test_db):
    """Test Question 5: How did revenue change between two months?"""
    # Compare May and June 2026
    res = query_revenue_change_between_months(month1="2026-05", month2="2026-06", db_path=setup_test_db)
    assert res["intent"] == "REVENUE_CHANGE_BETWEEN_MONTHS"
    assert res["figures"]["month1"] == "2026-05"
    assert res["figures"]["month2"] == "2026-06"
    assert res["figures"]["revenue1"] == 318500.0
    assert res["figures"]["revenue2"] == 217250.0
    assert res["figures"]["absolute_change"] == -101250.0
    assert res["figures"]["percentage_change"] == -31.79
    assert "decreased" in res["answer"]
