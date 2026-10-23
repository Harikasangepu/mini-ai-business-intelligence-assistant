"""FastAPI backend application for the Mini AI Business Intelligence Assistant."""
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.database import get_db_connection
from app.data_loader import load_csv_to_sqlite
from app.llm_service import process_business_question

logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# Lifespan Management (Auto-initialization of DB)
# -------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: ensure DB exists and is populated
    try:
        if not settings.DATABASE_PATH.exists():
            logger.info("Database file not found on startup. Running initial ingestion...")
            load_csv_to_sqlite()
        else:
            # Check row count
            conn = get_db_connection(read_only=True)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS cnt FROM sales;")
            count = cursor.fetchone()["cnt"]
            conn.close()
            if count == 0:
                logger.info("Database empty. Populating with sales data...")
                load_csv_to_sqlite()
    except Exception as e:
        logger.error(f"Error during startup data initialization: {e}")
        
    yield
    # On shutdown (cleanup if needed)

# -------------------------------------------------------------
# FastAPI App Setup
# -------------------------------------------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Intelligent natural-language query assistant for sales business intelligence.",
    lifespan=lifespan
)

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# Pydantic Schemas
# -------------------------------------------------------------
class QuestionRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Natural language question about sales analytics.",
        json_schema_extra={"example": "What is the total revenue?"}
    )

class AskResponse(BaseModel):
    status: str
    question: str
    intent: str
    answer: str
    figures: Dict[str, Any]
    supporting_table: List[Dict[str, Any]]
    sql_query: str
    chart_type: Optional[str] = None
    confidence: float
    source: str

class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    total_sales_records: int
    llm_configured: bool
    llm_provider: str
    message: str

# -------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------
@app.get("/", tags=["General"])
def read_root():
    """Root metadata endpoint."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "health_url": "/health"
    }

@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Verify backend health, database connectivity, and LLM configuration."""
    db_connected = False
    record_count = 0
    message = "Service operational."
    
    try:
        conn = get_db_connection(read_only=True)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM sales;")
        row = cursor.fetchone()
        record_count = row["total"] if row else 0
        conn.close()
        db_connected = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        message = f"Database connectivity issue: {str(e)}"
        
    llm_ready = bool(
        (settings.LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY) or
        (settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY)
    )
    
    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        database_connected=db_connected,
        total_sales_records=record_count,
        llm_configured=llm_ready,
        llm_provider=settings.LLM_PROVIDER if llm_ready else "deterministic fallback (no key)",
        message=message
    )

@app.post("/ask", response_model=AskResponse, tags=["Analytics"])
def ask_question(payload: QuestionRequest):
    """Process a natural-language business question and return answers supported by database queries."""
    clean_q = payload.question.strip()
    if not clean_q:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The question field cannot be empty or whitespace."
        )
        
    try:
        result = process_business_question(clean_q)
        return AskResponse(
            status=result.get("status", "success"),
            question=clean_q,
            intent=result.get("intent", "UNKNOWN"),
            answer=result.get("answer", ""),
            figures=result.get("figures", {}),
            supporting_table=result.get("supporting_table", []),
            sql_query=result.get("sql_query", ""),
            chart_type=result.get("chart_type"),
            confidence=float(result.get("confidence", 0.0)),
            source=result.get("source", "Unknown")
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Unhandled error in /ask: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your question: {str(e)}"
        )
