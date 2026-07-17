import pytest
from httpx import AsyncClient

from app.core.config import settings

pytestmark = pytest.mark.asyncio


async def test_health_check_endpoint(client: AsyncClient) -> None:
    """Verifies the health check API verifies database connection and returns OK status."""
    response = await client.get(f"{settings.API_V1_STR}/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["database"] == "healthy"
    assert data["document_store"] == "healthy"
