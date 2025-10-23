"""HTTP client dependency for specialized for the Turborepo cache proxying."""

from __future__ import annotations

import httpx

from ..config import config

__all__ = [
    "ProxyClientDependency",
    "proxy_client",
]


class ProxyClientDependency:
    """Provides an ``httpx.AsyncClient`` as a dependency specialized for
    Turborepo cache proxying.

    Notes
    -----
    The application must call ``proxy_client.aclose()`` in the
    application lifespan hook:

    .. code-block:: python

       from collections.abc import AsyncGenerator
       from contextlib import asynccontextmanager

       from fastapi import FastAPI


       @asynccontextmanager
       async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
           yield
           await proxy_client.aclose()


       app = FastAPI(lifespan=lifespan)
    """

    def __init__(self) -> None:
        self.http_client: httpx.AsyncClient | None = None

    async def __call__(self) -> httpx.AsyncClient:
        """Return the cached ``httpx.AsyncClient``."""
        if not self.http_client:
            timeout = httpx.Timeout(
                connect=5.0,
                read=None,  # No read timeout for large downloads
                write=None,  # No write timeout for large uploads
                pool=10.0,
            )
            limits = httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0,
            )
            self.http_client = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                base_url=str(config.cache_url),
            )
        return self.http_client

    async def aclose(self) -> None:
        """Close the ``httpx.AsyncClient``."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None


proxy_client = ProxyClientDependency()
"""The dependency that will return the HTTP client."""
