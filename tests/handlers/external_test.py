"""Tests for the turborepocacheproxy.handlers.external module and routes."""

from __future__ import annotations

import pytest
import respx
from httpx import AsyncClient, Response

from turborepocacheproxy.config import config

# Test fixtures
ARTIFACT_ID = "a" * 40  # 40-character hex string (realistic artifact hash)
ARTIFACT_DATA = b"test cache artifact data content"
TEAM_ID = "test-team"
BACKEND_URL = str(config.cache_url)
CACHE_TOKEN = config.cache_token.get_secret_value()


@pytest.mark.asyncio
async def test_artifact_upload(client: AsyncClient) -> None:
    """Test PUT /turborepo-cache/v8/artifacts/{hash} - Upload artifact."""
    async with respx.mock:
        # Mock backend response
        route = respx.route(
            method="PUT",
            url__regex=rf".*{ARTIFACT_ID}.*teamId={TEAM_ID}",
        ).mock(return_value=Response(200))

        # Client uploads artifact to proxy
        response = await client.put(
            f"/turborepo-cache/v8/artifacts/{ARTIFACT_ID}",
            params={"teamId": TEAM_ID},
            headers={"Content-Type": "application/octet-stream"},
            content=ARTIFACT_DATA,
        )

        # Verify response
        assert response.status_code == 200

        # Verify backend received the request
        assert route.called
        assert route.call_count == 1

        # Verify backend received correct data
        backend_request = route.calls[0].request
        assert await backend_request.aread() == ARTIFACT_DATA
        content_type = backend_request.headers["content-type"]
        assert content_type == "application/octet-stream"
        auth_header = backend_request.headers["authorization"]
        assert auth_header == f"Bearer {CACHE_TOKEN}"


@pytest.mark.asyncio
async def test_artifact_download(client: AsyncClient) -> None:
    """Test GET /turborepo-cache/v8/artifacts/{hash} - Download artifact."""
    async with respx.mock:
        # Mock backend to return artifact data
        respx.route(
            method="GET",
            url__regex=rf".*{ARTIFACT_ID}.*teamId={TEAM_ID}",
        ).mock(
            return_value=Response(
                200,
                headers={"content-type": "application/octet-stream"},
                content=ARTIFACT_DATA,
            )
        )

        # Client downloads artifact from proxy
        response = await client.get(
            f"/turborepo-cache/v8/artifacts/{ARTIFACT_ID}",
            params={"teamId": TEAM_ID},
        )

        # Verify response
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert response.content == ARTIFACT_DATA


@pytest.mark.asyncio
async def test_artifact_head(client: AsyncClient) -> None:
    """Test HEAD /turborepo-cache/v8/artifacts/{hash} - Check existence."""
    async with respx.mock:
        # Mock backend to indicate artifact exists
        route = respx.route(
            method="HEAD",
            url__regex=rf".*{ARTIFACT_ID}.*teamId={TEAM_ID}",
        ).mock(
            return_value=Response(
                200,
                headers={"content-type": "application/octet-stream"},
            )
        )

        # Client checks if artifact exists
        response = await client.head(
            f"/turborepo-cache/v8/artifacts/{ARTIFACT_ID}",
            params={"teamId": TEAM_ID},
        )

        # Verify response
        assert response.status_code == 200
        assert response.content == b""  # HEAD responses have no body

        # Verify backend was called
        assert route.called


@pytest.mark.asyncio
async def test_artifact_not_found(client: AsyncClient) -> None:
    """Test GET /turborepo-cache/v8/artifacts/{hash} - Artifact not found."""
    async with respx.mock:
        # Mock backend to return 404
        respx.route(
            method="GET",
            url__regex=rf".*{ARTIFACT_ID}.*teamId={TEAM_ID}",
        ).mock(
            return_value=Response(
                404,
                json={
                    "statusCode": 404,
                    "error": "Not Found",
                    "message": "Artifact not found",
                },
            )
        )

        # Client requests non-existent artifact
        response = await client.get(
            f"/turborepo-cache/v8/artifacts/{ARTIFACT_ID}",
            params={"teamId": TEAM_ID},
        )

        # Verify 404 passes through
        assert response.status_code == 404
        data = response.json()
        assert data["statusCode"] == 404
        assert data["message"] == "Artifact not found"


@pytest.mark.asyncio
async def test_cache_status(client: AsyncClient) -> None:
    """Test GET /turborepo-cache/v8/artifacts/status - Cache status."""
    async with respx.mock:
        # Mock backend status response
        respx.route(
            method="GET",
            url__regex=r".*/v8/artifacts/status",
        ).mock(
            return_value=Response(
                200,
                json={"status": "enabled", "version": "1.2.3"},
            )
        )

        # Client requests cache status
        response = await client.get("/turborepo-cache/v8/artifacts/status")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "enabled"
        assert data["version"] == "1.2.3"


@pytest.mark.asyncio
async def test_analytics_events(client: AsyncClient) -> None:
    """Test POST /turborepo-cache/v8/artifacts/events - Analytics."""
    async with respx.mock:
        event_data = b'{"sessionId":"abc","source":"local","event":"hit"}'

        # Mock backend to accept events
        route = respx.route(
            method="POST",
            url__regex=r".*/v8/artifacts/events",
        ).mock(return_value=Response(200, json={}))

        # Client posts analytics event
        response = await client.post(
            "/turborepo-cache/v8/artifacts/events",
            content=event_data,
        )

        # Verify response
        assert response.status_code == 200
        assert response.json() == {}

        # Verify backend received the request
        assert route.called


@pytest.mark.asyncio
async def test_path_prefix_stripping(client: AsyncClient) -> None:
    """Test that /turborepo-cache prefix is stripped before backend."""
    async with respx.mock:
        # Mock backend - should receive path WITHOUT prefix
        route = respx.route(
            method="GET",
            url__regex=rf".*{ARTIFACT_ID}.*teamId={TEAM_ID}",
        ).mock(return_value=Response(200, content=ARTIFACT_DATA))

        # Client requests with prefix
        response = await client.get(
            f"/turborepo-cache/v8/artifacts/{ARTIFACT_ID}",
            params={"teamId": TEAM_ID},
        )

        # Verify response succeeded
        assert response.status_code == 200

        # Verify backend was called with correct path (no prefix)
        assert route.called
        backend_request = route.calls[0].request
        # Verify path does NOT contain /turborepo-cache
        assert "/turborepo-cache" not in str(backend_request.url.path)
        assert backend_request.url.path == f"/v8/artifacts/{ARTIFACT_ID}"


@pytest.mark.asyncio
async def test_double_slash_normalization(client: AsyncClient) -> None:
    """Test that double slashes after prefix are normalized.

    This handles cases where TURBO_API ends with a trailing slash
    and the client appends a path starting with a slash, resulting
    in URLs like /turborepo-cache//v8/artifacts/... instead of
    /turborepo-cache/v8/artifacts/...
    """
    async with respx.mock:
        # Mock backend - should receive normalized path with single slash
        route = respx.route(
            method="GET",
            url__regex=rf".*{ARTIFACT_ID}.*teamId={TEAM_ID}",
        ).mock(return_value=Response(200, content=ARTIFACT_DATA))

        # Client requests with double slash after prefix
        # (simulating TURBO_API misconfiguration)
        response = await client.get(
            f"/turborepo-cache//v8/artifacts/{ARTIFACT_ID}",
            params={"teamId": TEAM_ID},
        )

        # Verify response succeeded
        assert response.status_code == 200

        # Verify backend received normalized path (single slash)
        assert route.called
        backend_request = route.calls[0].request
        assert backend_request.url.path == f"/v8/artifacts/{ARTIFACT_ID}"
        # Ensure NO double slashes in the backend path
        assert "//" not in backend_request.url.path


@pytest.mark.asyncio
async def test_query_parameter_variations(client: AsyncClient) -> None:
    """Test that query parameters (team, teamId, slug) are preserved."""
    test_cases = [
        ({"team": "my-team"}, "team=my-team"),
        ({"teamId": "my-team-id"}, "teamId=my-team-id"),
        ({"slug": "my-slug"}, "slug=my-slug"),
    ]

    for params, query_pattern in test_cases:
        async with respx.mock:
            # Mock backend for each variation
            route = respx.route(
                method="GET",
                url__regex=rf".*{ARTIFACT_ID}.*{query_pattern}",
            ).mock(return_value=Response(200, content=ARTIFACT_DATA))

            # Client requests with specific query param
            response = await client.get(
                f"/turborepo-cache/v8/artifacts/{ARTIFACT_ID}",
                params=params,
            )

            # Verify response succeeded
            assert response.status_code == 200

            # Verify backend received the query parameter
            assert route.called
            backend_request = route.calls[0].request
            for key, value in params.items():
                assert backend_request.url.params.get(key) == value


@pytest.mark.asyncio
async def test_header_filtering(client: AsyncClient) -> None:
    """Test that hop-by-hop headers are NOT forwarded to backend."""
    async with respx.mock:
        # Mock backend
        route = respx.route(
            method="GET",
            url__regex=rf".*{ARTIFACT_ID}.*teamId={TEAM_ID}",
        ).mock(return_value=Response(200, content=ARTIFACT_DATA))

        # Client sends hop-by-hop headers that should be filtered
        response = await client.get(
            f"/turborepo-cache/v8/artifacts/{ARTIFACT_ID}",
            params={"teamId": TEAM_ID},
            headers={
                "Connection": "keep-alive",
                "Keep-Alive": "timeout=5",
                "Transfer-Encoding": "chunked",
                "Upgrade": "websocket",
                "X-Custom-Header": "should-pass-through",
            },
        )

        # Verify response succeeded
        assert response.status_code == 200

        # Verify request was made
        assert route.called
        backend_request = route.calls[0].request
        backend_headers = dict(backend_request.headers)

        # Verify hop-by-hop headers were filtered
        # Note: httpx may add its own connection/keep-alive headers,
        # but we verify that client-specific headers like upgrade are filtered
        assert "upgrade" not in backend_headers

        # Verify custom headers pass through (this proves filtering works)
        custom_header = backend_headers.get("x-custom-header")
        assert custom_header == "should-pass-through"


@pytest.mark.asyncio
async def test_authorization_replacement(client: AsyncClient) -> None:
    """Test that client's Authorization is replaced with cache token."""
    async with respx.mock:
        # Mock backend
        route = respx.route(
            method="GET",
            url__regex=rf".*{ARTIFACT_ID}.*teamId={TEAM_ID}",
        ).mock(return_value=Response(200, content=ARTIFACT_DATA))

        # Client sends its own Authorization header (e.g., Gafaelfawr token)
        response = await client.get(
            f"/turborepo-cache/v8/artifacts/{ARTIFACT_ID}",
            params={"teamId": TEAM_ID},
            headers={"Authorization": "Bearer client-token-xyz"},
        )

        # Verify response succeeded
        assert response.status_code == 200

        # Verify backend received static cache token, NOT client's token
        assert route.called
        backend_request = route.calls[0].request
        backend_auth = backend_request.headers["authorization"]
        assert backend_auth == f"Bearer {CACHE_TOKEN}"
        assert backend_auth != "Bearer client-token-xyz"


@pytest.mark.asyncio
async def test_backend_connection_error(client: AsyncClient) -> None:
    """Test error handling when backend is unavailable."""
    async with respx.mock:
        # Mock backend to raise connection error
        respx.route(
            method="GET",
            url__regex=rf".*{ARTIFACT_ID}.*teamId={TEAM_ID}",
        ).mock(side_effect=Exception("Connection refused"))

        # Client attempts to download artifact
        response = await client.get(
            f"/turborepo-cache/v8/artifacts/{ARTIFACT_ID}",
            params={"teamId": TEAM_ID},
        )

        # Verify proxy returns 500 error
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert "Connection refused" in data["error"]
