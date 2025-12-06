"""
Entry point for notion-learning-sync service.

Run with:
    uvicorn main:app --reload --port 8100
    python main.py
"""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from config import get_settings
from src.api.main import app

settings = get_settings()

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
