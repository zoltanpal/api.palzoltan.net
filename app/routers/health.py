"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
def read_root():
    """Root endpoint."""
    return {"message": "Hello from api-palzoltan-net-v3!"}
