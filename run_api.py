"""Convenience runner script for the FastAPI backend API."""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"Starting {settings.PROJECT_NAME} backend on http://{settings.API_HOST}:{settings.API_PORT} ...")
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False
    )
