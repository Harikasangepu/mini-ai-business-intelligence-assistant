"""Configuration module for the Mini AI Business Intelligence Assistant."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "Mini AI Business Intelligence Assistant"
    VERSION: str = "1.0.0"
    
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    
    DEFAULT_CSV_PATH: Path = DATA_DIR / "sales_data.csv"
    CSV_PATH: Path = Path(os.getenv("CSV_PATH", str(DEFAULT_CSV_PATH)))
    
    DEFAULT_DB_PATH: Path = DATA_DIR / "sales.db"
    DATABASE_PATH: Path = Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH)))
    
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8001"))
    
    # LLM Settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
    
    # Known fixed catalog price for imputation
    LAPTOP_STAND_CATALOG_PRICE: float = 1200.0

settings = Settings()
