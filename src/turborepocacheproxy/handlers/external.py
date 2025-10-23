"""Handlers for the app's external root, ``/turborepo-cache/``."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from httpx import AsyncClient
from safir.dependencies.logger import logger_dependency
from safir.slack.webhook import SlackRouteErrorHandler
from starlette.background import BackgroundTask
from starlette.datastructures import Headers
from structlog.stdlib import BoundLogger

from ..config import config
from ..dependencies.proxyclient import proxy_client

__all__ = ["external_router"]

external_router = APIRouter(route_class=SlackRouteErrorHandler)
"""FastAPI router for all external handlers."""


@external_router.api_route(
    "/{path:path}",
    methods=["GET", "HEAD", "POST", "PUT"],
    description=(
        "Proxy requests to the Turborepo remote cache backend. This "
        "handler streams requests and responses, replacing authentication "
        "headers with the static Bearer token for the turborepo cache backend."
    ),
)
async def handle_proxy_request(
    request: Request,
    path: str,
    logger: Annotated[BoundLogger, Depends(logger_dependency)],
    proxy_client: Annotated[AsyncClient, Depends(proxy_client)],
) -> Response:
    """Proxy requests to the Turborepo remote cache backend.

    This handler intercepts all requests to the proxy's path prefix,
    strips the prefix, replaces authentication headers, and forwards
    the request to the backend cache while streaming the response back
    to the client.

    Parameters
    ----------
    request
        The incoming FastAPI request.
    path
        The catch-all path from the route (not used directly).
    logger
        Structured logger for request tracking.
    proxy_client
        HTTP client configured for backend requests.

    Returns
    -------
    Response
        Streamed response from the backend cache, or JSON error on failure.

    Notes
    -----
    - Strips the path prefix (e.g., ``/turborepo-cache``) from requests
    - Filters hop-by-hop headers (Connection, Host, Authorization, etc.)
    - Adds static Bearer token for backend authentication
    - Preserves query parameters (teamId, team, slug, etc.)
    - Streams request and response bodies for efficient artifact transfer
    - Returns 500 JSON error if backend is unreachable
    """
    try:
        # Strip proxy path prefix
        backend_path = request.url.path.removeprefix(config.path_prefix)
        # Normalize double slashes after prefix
        # (e.g., //v8/artifacts -> /v8/artifacts)
        backend_path = "/" + backend_path.lstrip("/")

        url = httpx.URL(path=backend_path, query=request.url.query.encode())

        # Add authentication for ducktors
        headers = filter_request_headers(request.headers)
        headers.append(
            (
                b"Authorization",
                f"Bearer {config.cache_token.get_secret_value()}".encode(),
            )
        )

        # Stream request
        proxy_request = proxy_client.build_request(
            method=request.method,
            url=url,
            headers=headers,
            content=request.stream(),
        )

        # Stream response - NO modification needed!
        r = await proxy_client.send(proxy_request, stream=True)

        return StreamingResponse(
            r.aiter_raw(),
            status_code=r.status_code,
            headers=r.headers,
            background=BackgroundTask(r.aclose),
        )

    except Exception as e:
        logger.exception(f"Proxy error: {request.method} {path}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# Headers to exclude when forwarding
HOP_BY_HOP_HEADERS = {
    b"connection",
    b"keep-alive",
    b"proxy-authenticate",
    b"proxy-authorization",
    b"te",
    b"trailers",
    b"transfer-encoding",
    b"upgrade",
    b"host",
    b"authorization",
}


def filter_request_headers(headers: Headers) -> list[tuple[bytes, bytes]]:
    """Filter hop-by-hop headers."""
    return [
        (k, v) for k, v in headers.raw if k.lower() not in HOP_BY_HOP_HEADERS
    ]
