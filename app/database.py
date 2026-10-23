"""Database connection and initialization module."""
import sqlite3
from pathlib import Path
from typing import Optional
from app.config import settings

def get_db_connection(db_path: Optional[Path] = None, read_only: bool = False) -> sqlite3.Connection:
    """Create and return a SQLite database connection.
    
    If read_only is True, opens the SQLite database in URI read-only mode to prevent
    accidental or unauthorized writes.
    """
    path = Path(db_path or settings.DATABASE_PATH).resolve()
    
    # Ensure directory exists for write mode
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
    else:
        if not path.exists():
            raise FileNotFoundError(f"Database not found at {path}. Run data ingestion first.")
        # Open in URI read-only mode
        uri = f"file:{path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize the SQLite database schema with appropriate tables and indexes."""
    conn = get_db_connection(db_path=db_path, read_only=False)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            transaction_id TEXT PRIMARY KEY,
            order_date TEXT NOT NULL,
            product TEXT NOT NULL,
            category TEXT NOT NULL,
            region TEXT NOT NULL,
            sales_channel TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            discount_amount REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL,
            line_revenue REAL NOT NULL,
            is_imputed INTEGER NOT NULL DEFAULT 0
        );
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_order_date ON sales(order_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_region ON sales(region);")
    
    conn.commit()
    conn.close()
