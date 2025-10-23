"""Tests for the turborepocacheproxy.handlers.internal module and routes."""

from __future__ import annotations

import pytest
import respx
from httpx import AsyncClient, Response

from turborepocacheproxy.config import config

BACKEND_URL = str(config.cache_url)


@pytest.mark.asyncio
async def test_get_index(client: AsyncClient) -> None:
    """Test ``GET /``."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == config.name
    assert isinstance(data["version"], str)
    assert isinstance(data["description"], str)
    assert isinstance(data["repository_url"], str)


@pytest.mark.asyncio
async def test_healthcheck_backend_healthy(client: AsyncClient) -> None:
    """Test GET /healthcheck when backend is healthy."""
    async with respx.mock:
        # Mock backend status endpoint to return healthy response
        respx.route(
            method="GET",
            url__regex=r".*/v8/artifacts/status",
        ).mock(
            return_value=Response(
                200,
                json={"status": "enabled", "version": "1.0.0"},
            )
        )

        # Request healthcheck
        response = await client.get("/healthcheck")

        # Verify healthy response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["cache_backend"] == "available"
        assert data["cache_url"] == BACKEND_URL


@pytest.mark.asyncio
async def test_healthcheck_backend_unavailable(client: AsyncClient) -> None:
    """Test GET /healthcheck when backend is unreachable."""
    async with respx.mock:
        # Mock backend to raise connection error
        respx.route(
            method="GET",
            url__regex=r".*/v8/artifacts/status",
        ).mock(side_effect=Exception("Connection refused"))

        # Request healthcheck
        response = await client.get("/healthcheck")

        # Verify unhealthy response
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["cache_backend"] == "unavailable"
        assert data["cache_url"] == BACKEND_URL


@pytest.mark.asyncio
async def test_healthcheck_backend_error(client: AsyncClient) -> None:
    """Test GET /healthcheck when backend returns error."""
    async with respx.mock:
        # Mock backend to return 500 error
        respx.route(
            method="GET",
            url__regex=r".*/v8/artifacts/status",
        ).mock(
            return_value=Response(
                500,
                json={"error": "Internal server error"},
            )
        )

        # Request healthcheck
        response = await client.get("/healthcheck")

        # Verify unhealthy response
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["cache_backend"] == "unavailable"
        assert data["cache_url"] == BACKEND_URL
