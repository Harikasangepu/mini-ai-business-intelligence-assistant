"""Unit tests for LLM interpretation and deterministic fallback logic."""
import pytest
from app.llm_service import (
    interpret_with_deterministic_fallback,
    extract_months_from_text,
    process_business_question,
    INTENT_TOTAL_REVENUE,
    INTENT_HIGHEST_REVENUE_PRODUCT,
    INTENT_MONTHLY_REVENUE_TREND,
    INTENT_HIGHEST_SALES_REGION,
    INTENT_REVENUE_CHANGE_BETWEEN_MONTHS,
    INTENT_UNKNOWN
)

def test_extract_months_from_text():
    """Verify month parsing from varied text expressions."""
    # Named months
    m1, m2 = extract_months_from_text("compare revenue from January to March")
    assert m1 == "2026-01"
    assert m2 == "2026-03"
    
    # ISO months
    m1, m2 = extract_months_from_text("difference between 2026-02 and 2026-04")
    assert m1 == "2026-02"
    assert m2 == "2026-04"

def test_fallback_intent_mapping():
    """Verify deterministic fallback correctly classifies the 5 required questions."""
    # Q1
    res = interpret_with_deterministic_fallback("What is the total revenue?")
    assert res["intent"] == INTENT_TOTAL_REVENUE
    assert "Fallback Engine" in res["source"]
    
    # Q2
    res = interpret_with_deterministic_fallback("Which product generated the highest revenue?")
    assert res["intent"] == INTENT_HIGHEST_REVENUE_PRODUCT
    
    # Q3
    res = interpret_with_deterministic_fallback("What is the monthly revenue trend?")
    assert res["intent"] == INTENT_MONTHLY_REVENUE_TREND
    
    # Q4
    res = interpret_with_deterministic_fallback("Which region generated the highest sales?")
    assert res["intent"] == INTENT_HIGHEST_SALES_REGION
    
    # Q5
    res = interpret_with_deterministic_fallback("How did revenue change between two months?")
    assert res["intent"] == INTENT_REVENUE_CHANGE_BETWEEN_MONTHS
    
    # Unsupported / Edge
    res = interpret_with_deterministic_fallback("Show me weather forecast")
    assert res["intent"] == INTENT_UNKNOWN

def test_process_business_question_unknown():
    """Verify graceful handling for unsupported questions."""
    res = process_business_question("Who is the CEO of Google?")
    assert res["status"] == "unsupported"
    assert res["intent"] == INTENT_UNKNOWN
    assert "could not map your query" in res["answer"].lower()
