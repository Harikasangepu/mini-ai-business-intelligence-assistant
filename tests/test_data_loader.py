"""Unit tests for data cleaning and SQLite loading."""
import pytest
import sqlite3
import pandas as pd
from pathlib import Path
from app.data_loader import clean_sales_dataframe, load_csv_to_sqlite
from app.config import settings
from app.database import get_db_connection

def test_clean_sales_dataframe_rules():
    """Verify data cleaning rules on raw sales dataframe."""
    df_raw = pd.read_csv(settings.CSV_PATH)
    df_clean, stats = clean_sales_dataframe(df_raw)
    
    # 1. Total row count matches
    assert stats["total_raw_rows"] == 51
    assert len(df_clean) == 51
    
    # 2. Imputation check: TXN0051 (Laptop Stand) should be imputed with 1200.0
    txn51 = df_clean[df_clean["transaction_id"] == "TXN0051"].iloc[0]
    assert txn51["unit_price"] == 1200.0
    assert txn51["is_imputed"] == 1
    assert stats["imputed_rows_count"] == 1
    
    # 3. Returned status check: TXN0033
    txn33 = df_clean[df_clean["transaction_id"] == "TXN0033"].iloc[0]
    assert txn33["status"].lower() == "returned"
    assert stats["returned_orders_count"] == 1
    
    # 4. Zero quantity check: TXN0034
    txn34 = df_clean[df_clean["transaction_id"] == "TXN0034"].iloc[0]
    assert txn34["quantity"] == 0
    assert txn34["line_revenue"] == 0.0
    assert stats["zero_quantity_count"] == 1
    
    # 5. Date format standardized to YYYY-MM-DD
    sample_date = df_clean["order_date"].iloc[0]
    assert len(sample_date.split("-")) == 3
    assert len(sample_date.split("-")[0]) == 4  # Year is 4 digits
    
    # 6. Total net revenue calculation
    # 51 rows - 1 returned - 1 zero quantity = 49 completed valid rows
    assert stats["valid_completed_rows"] == 49
    assert stats["total_net_revenue"] == 1445200.0

def test_load_csv_to_sqlite(tmp_path):
    """Test loading data into a fresh temporary SQLite database."""
    test_db = tmp_path / "test_sales.db"
    stats = load_csv_to_sqlite(csv_path=settings.CSV_PATH, db_path=test_db, overwrite=True)
    
    assert stats["rows_inserted"] == 51
    
    # Verify records via SQLite query
    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sales;")
    count = cursor.fetchone()[0]
    assert count == 51
    
    # Verify net revenue directly in SQLite
    cursor.execute("""
        SELECT SUM(line_revenue) 
        FROM sales 
        WHERE status = 'Completed' AND quantity > 0;
    """)
    db_revenue = cursor.fetchone()[0]
    assert db_revenue == 1445200.0
    conn.close()
