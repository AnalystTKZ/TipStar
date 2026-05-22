from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import FRONTEND_ORIGIN


def register_middleware(app: FastAPI) -> None:
    """Register CORS and any other global middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[FRONTEND_ORIGIN, "http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
