"""Data ingestion and cleaning pipeline for the Sales dataset."""
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import pandas as pd
from app.config import settings
from app.database import init_db, get_db_connection

logger = logging.getLogger(__name__)

def clean_sales_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Clean the raw sales dataframe according to documented business rules.
    
    Rules applied:
    1. Strip leading/trailing whitespace from column names and string columns.
    2. Impute missing Unit_price for 'Laptop Stand' using master catalog unit price (1200.0).
       Flag imputed rows with is_imputed = 1.
    3. Standardize Order_date from DD-MM-YYYY to ISO-8601 YYYY-MM-DD for SQLite compatibility.
    4. Validate numerical fields (Quantity, Unit_price, Discount_amount).
    5. Compute line_revenue = (Quantity * Unit_price) - Discount_amount.
    6. Retain all rows in database for auditability while tracking status (e.g., 'Returned')
       and zero quantity orders.
    """
    df_clean = df.copy()
    
    # Standardize column names
    df_clean.columns = [col.strip() for col in df_clean.columns]
    
    # Map expected column names
    col_mapping = {
        'Transaction_Id': 'transaction_id',
        'Order_date': 'order_date',
        'Product': 'product',
        'Category': 'category',
        'Region': 'region',
        'Sales_channel': 'sales_channel',
        'Quantity': 'quantity',
        'Unit_price': 'unit_price',
        'Discount_amount': 'discount_amount',
        'Status': 'status'
    }
    df_clean = df_clean.rename(columns=col_mapping)
    
    # Clean string columns
    for str_col in ['transaction_id', 'product', 'category', 'region', 'sales_channel', 'status']:
        if str_col in df_clean.columns:
            df_clean[str_col] = df_clean[str_col].astype(str).str.strip()
            
    # Track imputation flag
    df_clean['is_imputed'] = 0
    
    # Convert numerical columns
    df_clean['quantity'] = pd.to_numeric(df_clean['quantity'], errors='coerce').fillna(0).astype(int)
    df_clean['discount_amount'] = pd.to_numeric(df_clean['discount_amount'], errors='coerce').fillna(0.0).astype(float)
    df_clean['unit_price'] = pd.to_numeric(df_clean['unit_price'], errors='coerce')
    
    # Rule: Missing Unit Price Imputation
    # If Product is 'Laptop Stand' and unit_price is NaN, impute with catalog price
    missing_price_mask = df_clean['unit_price'].isna()
    laptop_stand_mask = missing_price_mask & (df_clean['product'].str.lower() == 'laptop stand')
    
    if laptop_stand_mask.any():
        df_clean.loc[laptop_stand_mask, 'unit_price'] = settings.LAPTOP_STAND_CATALOG_PRICE
        df_clean.loc[laptop_stand_mask, 'is_imputed'] = 1
        
    # Any remaining un-imputable prices default to 0.0 with warning
    remaining_missing = df_clean['unit_price'].isna()
    if remaining_missing.any():
        logger.warning(f"Found {remaining_missing.sum()} rows with unresolvable unit prices. Defaulting to 0.0")
        df_clean.loc[remaining_missing, 'unit_price'] = 0.0
        
    # Rule: Parse dates from DD-MM-YYYY to ISO YYYY-MM-DD
    parsed_dates = pd.to_datetime(df_clean['order_date'], format='%d-%m-%Y', errors='coerce')
    df_clean['order_date'] = parsed_dates.dt.strftime('%Y-%m-%d')
    
    # Rule: Compute line_revenue = (Quantity * Unit_price) - Discount_amount
    df_clean['line_revenue'] = (df_clean['quantity'] * df_clean['unit_price']) - df_clean['discount_amount']
    # Prevent negative revenue if discount unexpectedly exceeded line total
    df_clean['line_revenue'] = df_clean['line_revenue'].clip(lower=0.0)
    
    # Generate audit metrics
    total_raw_rows = len(df)
    imputed_rows_count = int(df_clean['is_imputed'].sum())
    zero_qty_count = int((df_clean['quantity'] <= 0).sum())
    returned_count = int((df_clean['status'].str.lower() == 'returned').sum())
    
    # Valid completed transactions for analytics
    completed_valid_mask = (df_clean['status'].str.lower() == 'completed') & (df_clean['quantity'] > 0)
    net_revenue = float(df_clean.loc[completed_valid_mask, 'line_revenue'].sum())
    gross_revenue = float(df_clean.loc[df_clean['quantity'] > 0, 'line_revenue'].sum())
    
    stats = {
        "total_raw_rows": total_raw_rows,
        "imputed_rows_count": imputed_rows_count,
        "zero_quantity_count": zero_qty_count,
        "returned_orders_count": returned_count,
        "valid_completed_rows": int(completed_valid_mask.sum()),
        "total_net_revenue": net_revenue,
        "total_gross_revenue": gross_revenue
    }
    
    return df_clean, stats

def load_csv_to_sqlite(
    csv_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
    overwrite: bool = True
) -> Dict[str, Any]:
    """Ingest sales CSV into SQLite database table 'sales'."""
    c_path = Path(csv_path or settings.CSV_PATH).resolve()
    d_path = Path(db_path or settings.DATABASE_PATH).resolve()
    
    if not c_path.exists():
        raise FileNotFoundError(f"Sales CSV file not found at {c_path}")
        
    init_db(d_path)
    
    df_raw = pd.read_csv(c_path)
    df_clean, stats = clean_sales_dataframe(df_raw)
    
    conn = get_db_connection(d_path, read_only=False)
    try:
        cursor = conn.cursor()
        if overwrite:
            cursor.execute("DELETE FROM sales;")
            
        columns = [
            'transaction_id', 'order_date', 'product', 'category', 'region',
            'sales_channel', 'quantity', 'unit_price', 'discount_amount',
            'status', 'line_revenue', 'is_imputed'
        ]
        
        insert_sql = f"""
            INSERT OR REPLACE INTO sales ({', '.join(columns)})
            VALUES ({', '.join(['?'] * len(columns))})
        """
        
        records = df_clean[columns].values.tolist()
        cursor.executemany(insert_sql, records)
        conn.commit()
        stats["rows_inserted"] = len(records)
        logger.info(f"Successfully loaded {len(records)} records into SQLite at {d_path}")
    finally:
        conn.close()
        
    return stats

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    stats = load_csv_to_sqlite()
    print("Ingestion successful. Summary:", stats)
