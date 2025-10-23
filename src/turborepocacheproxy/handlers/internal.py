"""Internal HTTP handlers that serve relative to the root path, ``/``.

These handlers aren't externally visible since the app is available at a path,
``/turborepo-cache``. See `turborepocacheproxy.handlers.external` for
the external endpoint handlers.

These handlers should be used for monitoring, health checks, internal status,
or other information that should not be visible outside the Kubernetes cluster.
"""

from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from safir.metadata import Metadata, get_metadata
from safir.slack.webhook import SlackRouteErrorHandler

from ..config import config
from ..dependencies.proxyclient import proxy_client

__all__ = ["HealthCheck", "internal_router"]


class HealthCheck(BaseModel):
    """Health check response model."""

    status: Literal["healthy", "unhealthy"]
    """Overall health status of the service."""

    cache_backend: Literal["available", "unavailable"]
    """Availability status of the backend cache."""

    cache_url: str
    """URL of the backend cache being monitored."""


internal_router = APIRouter(route_class=SlackRouteErrorHandler)
"""FastAPI router for all internal handlers."""


@internal_router.get(
    "/",
    description=(
        "Return metadata about the running application. Can also be used as"
        "a health check. This route is not exposed outside the cluster and "
        "therefore cannot be used by external clients."
    ),
    include_in_schema=False,
    response_model_exclude_none=True,
    summary="Application metadata",
)
async def get_index() -> Metadata:
    return get_metadata(
        package_name="turborepo-cache-proxy",
        application_name=config.name,
    )


@internal_router.get(
    "/healthcheck",
    description=(
        "Check the health of the proxy and backend Turborepo cache. "
        "Returns 200 if the backend cache is available, 503 if unavailable. "
        "This route is not exposed outside the cluster."
    ),
    include_in_schema=False,
    response_model=HealthCheck,
    response_model_exclude_none=True,
    summary="Health check",
)
async def get_healthcheck(
    proxy_client: Annotated[httpx.AsyncClient, Depends(proxy_client)],
) -> HealthCheck | JSONResponse:
    """Check health of proxy and backend cache.

    Verifies that the backend Turborepo cache is reachable and responding
    by requesting its status endpoint.

    Parameters
    ----------
    proxy_client
        HTTP client configured for backend requests.

    Returns
    -------
    HealthCheck or JSONResponse
        Health status with 200 if healthy, 503 if unhealthy.
    """
    cache_url_str = str(config.cache_url)

    try:
        # Check backend cache status with a short timeout
        timeout = httpx.Timeout(5.0, connect=5.0)
        response = await proxy_client.get(
            "/v8/artifacts/status", timeout=timeout
        )

        if response.status_code == 200:
            # Backend is healthy
            return HealthCheck(
                status="healthy",
                cache_backend="available",
                cache_url=cache_url_str,
            )
        else:
            # Backend returned an error
            return JSONResponse(
                status_code=503,
                content=HealthCheck(
                    status="unhealthy",
                    cache_backend="unavailable",
                    cache_url=cache_url_str,
                ).model_dump(),
            )
    except Exception:
        # Backend is unreachable
        return JSONResponse(
            status_code=503,
            content=HealthCheck(
                status="unhealthy",
                cache_backend="unavailable",
                cache_url=cache_url_str,
            ).model_dump(),
        )
