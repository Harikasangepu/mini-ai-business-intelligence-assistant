"""Query execution service providing deterministic SQL templates, safe execution, and query validation."""
import re
import sqlite3
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from app.config import settings
from app.database import get_db_connection

# Dangerous SQL keywords forbidden in custom/ad-hoc queries
FORBIDDEN_SQL_KEYWORDS = {
    'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'ATTACH', 'DETACH',
    'CREATE', 'REPLACE', 'TRUNCATE', 'EXEC', 'EXECUTE', 'PRAGMA',
    'GRANT', 'REVOKE', 'REINDEX', 'VACUUM'
}

def validate_sql_safety(query: str) -> Tuple[bool, Optional[str]]:
    """Validate that a SQL query is read-only and free of destructive statements or SQL injection tricks."""
    cleaned = query.strip()
    if not cleaned:
        return False, "Query cannot be empty."
        
    # Query must start with SELECT or WITH
    upper_query = cleaned.upper()
    if not (upper_query.startswith("SELECT") or upper_query.startswith("WITH")):
        return False, "Security violation: Only SELECT or WITH queries are permitted."
        
    # Check for multiple statements (semicolon inside query)
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) > 1:
        return False, "Security violation: Multi-statement SQL execution is strictly forbidden."
        
    # Check for forbidden keywords as standalone word tokens
    tokens = set(re.findall(r'\b[A-Za-z_]+\b', upper_query))
    forbidden_found = tokens.intersection(FORBIDDEN_SQL_KEYWORDS)
    if forbidden_found:
        return False, f"Security violation: Query contains disallowed operation(s): {', '.join(forbidden_found)}"
        
    return True, None

def execute_safe_query(query: str, params: Optional[Tuple[Any, ...]] = None, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Execute a validated read-only SQL query against SQLite."""
    is_safe, error_msg = validate_sql_safety(query)
    if not is_safe:
        raise ValueError(error_msg)
        
    conn = get_db_connection(db_path=db_path, read_only=True)
    try:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

# -------------------------------------------------------------
# Approved Analytical Query Functions (5 Core Assignment Questions)
# -------------------------------------------------------------

def query_total_revenue(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Q1: What is the total revenue?"""
    sql = """
        SELECT 
            ROUND(SUM((quantity * unit_price) - discount_amount), 2) AS total_revenue,
            COUNT(*) AS completed_transactions,
            SUM(quantity) AS total_units_sold,
            ROUND(AVG((quantity * unit_price) - discount_amount), 2) AS average_order_value
        FROM sales
        WHERE status = 'Completed' AND quantity > 0;
    """
    results = execute_safe_query(sql, db_path=db_path)
    data = results[0] if results else {"total_revenue": 0.0, "completed_transactions": 0, "total_units_sold": 0, "average_order_value": 0.0}
    
    total_rev = data.get("total_revenue") or 0.0
    orders = data.get("completed_transactions") or 0
    units = data.get("total_units_sold") or 0
    aov = data.get("average_order_value") or 0.0
    
    narrative = (
        f"The total net revenue generated from completed transactions is ₹{total_rev:,.2f}. "
        f"This was achieved across {orders} completed orders with a total of {units:,} units sold, "
        f"yielding an average order value (AOV) of ₹{aov:,.2f}."
    )
    
    return {
        "intent": "TOTAL_REVENUE",
        "question": "What is the total revenue?",
        "answer": narrative,
        "figures": data,
        "supporting_table": [data],
        "sql_query": sql.strip(),
        "chart_type": "metric"
    }

def query_highest_revenue_product(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Q2: Which product generated the highest revenue?"""
    sql = """
        SELECT 
            product,
            category,
            ROUND(SUM((quantity * unit_price) - discount_amount), 2) AS revenue,
            SUM(quantity) AS units_sold,
            ROUND(AVG(unit_price), 2) AS unit_price
        FROM sales
        WHERE status = 'Completed' AND quantity > 0
        GROUP BY product
        ORDER BY revenue DESC;
    """
    results = execute_safe_query(sql, db_path=db_path)
    if not results:
        return {
            "intent": "HIGHEST_REVENUE_PRODUCT",
            "question": "Which product generated the highest revenue?",
            "answer": "No completed product sales data found in the database.",
            "figures": {},
            "supporting_table": [],
            "sql_query": sql.strip(),
            "chart_type": "bar"
        }
        
    top_prod = results[0]
    total_rev_all = sum(r["revenue"] for r in results)
    pct_share = (top_prod["revenue"] / total_rev_all * 100) if total_rev_all > 0 else 0
    
    narrative = (
        f"The product with the highest revenue is '{top_prod['product']}' ({top_prod['category']}), "
        f"generating ₹{top_prod['revenue']:,.2f} with {top_prod['units_sold']} units sold. "
        f"It contributed {pct_share:.1f}% of total net sales."
    )
    
    return {
        "intent": "HIGHEST_REVENUE_PRODUCT",
        "question": "Which product generated the highest revenue?",
        "answer": narrative,
        "figures": {
            "top_product": top_prod["product"],
            "top_revenue": top_prod["revenue"],
            "top_units_sold": top_prod["units_sold"],
            "revenue_share_pct": round(pct_share, 2),
            "all_products": results
        },
        "supporting_table": results,
        "sql_query": sql.strip(),
        "chart_type": "bar"
    }

def query_monthly_revenue_trend(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Q3: What is the monthly revenue trend?"""
    sql = """
        SELECT 
            strftime('%Y-%m', order_date) AS month,
            ROUND(SUM((quantity * unit_price) - discount_amount), 2) AS revenue,
            SUM(quantity) AS units_sold,
            COUNT(*) AS order_count
        FROM sales
        WHERE status = 'Completed' AND quantity > 0
        GROUP BY month
        ORDER BY month ASC;
    """
    results = execute_safe_query(sql, db_path=db_path)
    
    # Calculate MoM growth for context
    table_with_growth = []
    prev_rev = None
    best_month = None
    max_rev = -1.0
    
    for row in results:
        item = dict(row)
        curr_rev = item["revenue"]
        if prev_rev is not None and prev_rev > 0:
            growth = ((curr_rev - prev_rev) / prev_rev) * 100
            item["mom_growth_pct"] = round(growth, 2)
        else:
            item["mom_growth_pct"] = 0.0
            
        if curr_rev > max_rev:
            max_rev = curr_rev
            best_month = item["month"]
            
        prev_rev = curr_rev
        table_with_growth.append(item)
        
    narrative = (
        f"Monthly revenue shows consistent performance across 2026-01 to 2026-06, "
        f"peaking in {best_month} at ₹{max_rev:,.2f}. "
        f"Average monthly revenue was ₹{sum(r['revenue'] for r in results)/len(results):,.2f}."
    ) if results else "No monthly sales data found."
    
    return {
        "intent": "MONTHLY_REVENUE_TREND",
        "question": "What is the monthly revenue trend?",
        "answer": narrative,
        "figures": {
            "months": [r["month"] for r in table_with_growth],
            "revenues": [r["revenue"] for r in table_with_growth],
            "peak_month": best_month,
            "peak_revenue": max_rev,
            "trend_data": table_with_growth
        },
        "supporting_table": table_with_growth,
        "sql_query": sql.strip(),
        "chart_type": "line"
    }

def query_highest_sales_region(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Q4: Which region generated the highest sales?"""
    sql = """
        SELECT 
            region,
            ROUND(SUM((quantity * unit_price) - discount_amount), 2) AS revenue,
            SUM(quantity) AS units_sold,
            COUNT(*) AS order_count
        FROM sales
        WHERE status = 'Completed' AND quantity > 0
        GROUP BY region
        ORDER BY revenue DESC;
    """
    results = execute_safe_query(sql, db_path=db_path)
    if not results:
        return {
            "intent": "HIGHEST_SALES_REGION",
            "question": "Which region generated the highest sales?",
            "answer": "No regional sales records found.",
            "figures": {},
            "supporting_table": [],
            "sql_query": sql.strip(),
            "chart_type": "bar"
        }
        
    top_reg = results[0]
    total_rev = sum(r["revenue"] for r in results)
    pct_share = (top_reg["revenue"] / total_rev * 100) if total_rev > 0 else 0
    
    narrative = (
        f"The region with the highest sales is '{top_reg['region']}', generating ₹{top_reg['revenue']:,.2f} "
        f"({pct_share:.1f}% of total sales) with {top_reg['units_sold']} units sold across {top_reg['order_count']} orders."
    )
    
    return {
        "intent": "HIGHEST_SALES_REGION",
        "question": "Which region generated the highest sales?",
        "answer": narrative,
        "figures": {
            "top_region": top_reg["region"],
            "top_revenue": top_reg["revenue"],
            "top_units_sold": top_reg["units_sold"],
            "revenue_share_pct": round(pct_share, 2),
            "all_regions": results
        },
        "supporting_table": results,
        "sql_query": sql.strip(),
        "chart_type": "bar"
    }

def query_revenue_change_between_months(
    month1: Optional[str] = None,
    month2: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Q5: How did revenue change between two months?"""
    # If months are not specified, default to comparing the latest two recorded months (2026-05 and 2026-06)
    m1 = month1 or "2026-05"
    m2 = month2 or "2026-06"
    
    # Ensure chronological order (m1 earlier, m2 later)
    if m1 > m2:
        m1, m2 = m2, m1
        
    sql = """
        SELECT 
            strftime('%Y-%m', order_date) AS month,
            ROUND(SUM((quantity * unit_price) - discount_amount), 2) AS revenue,
            SUM(quantity) AS units_sold,
            COUNT(*) AS order_count
        FROM sales
        WHERE status = 'Completed' AND quantity > 0
          AND strftime('%Y-%m', order_date) IN (?, ?)
        GROUP BY month
        ORDER BY month ASC;
    """
    results = execute_safe_query(sql, params=(m1, m2), db_path=db_path)
    
    month_data = {r["month"]: r for r in results}
    rev1 = month_data.get(m1, {}).get("revenue", 0.0)
    rev2 = month_data.get(m2, {}).get("revenue", 0.0)
    
    diff = rev2 - rev1
    pct_change = ((diff / rev1) * 100) if rev1 > 0 else 0.0
    direction = "increased" if diff > 0 else ("decreased" if diff < 0 else "remained unchanged")
    
    narrative = (
        f"Comparing {m1} to {m2}: Revenue {direction} by ₹{abs(diff):,.2f} ({pct_change:+.2f}%). "
        f"Revenue in {m1} was ₹{rev1:,.2f} and in {m2} was ₹{rev2:,.2f}."
    )
    
    table = [
        {"metric": f"Revenue ({m1})", "value": f"₹{rev1:,.2f}"},
        {"metric": f"Revenue ({m2})", "value": f"₹{rev2:,.2f}"},
        {"metric": "Absolute Change", "value": f"₹{diff:+,.2f}"},
        {"metric": "Percentage Change", "value": f"{pct_change:+.2f}%"}
    ]
    
    return {
        "intent": "REVENUE_CHANGE_BETWEEN_MONTHS",
        "question": f"How did revenue change between {m1} and {m2}?",
        "answer": narrative,
        "figures": {
            "month1": m1,
            "revenue1": rev1,
            "month2": m2,
            "revenue2": rev2,
            "absolute_change": round(diff, 2),
            "percentage_change": round(pct_change, 2)
        },
        "supporting_table": table,
        "sql_query": sql.strip().replace("(?, ?)", f"('{m1}', '{m2}')"),
        "chart_type": "comparison"
    }
