"""FastAPI application entrypoint for Clinsight."""

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


app = FastAPI(
    title="Clinsight API",
    description="Clinical decision-support service for diabetes clinicians",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """Return health status of the API service."""
    return HealthResponse(status="ok")
