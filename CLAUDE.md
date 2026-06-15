# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

turborepo-cache-proxy is a FastAPI-based HTTP proxy that sits in front of a Turborepo remote cache (Ductors implementation). It exchanges Gafaelfawr access tokens for static Bearer tokens and rewrites paths to allow deployment with a URL prefix (e.g., `/turborepo-cache/`) while the backend expects root paths.

## Development Commands

### Setup

```bash
make init              # Set up dev environment (uv sync + pre-commit install)
make update            # Update dependencies and reinitialize
```

### Testing & Linting

```bash
uv run --only-group=tox tox run -e py          # Run pytest with coverage
uv run --only-group=tox tox run -e lint        # Run pre-commit linters
uv run --only-group=tox tox run -e typing      # Run mypy type checking
uv run --only-group=tox tox run -e coverage-report  # Generate coverage report
# Run all checks (used in CI):
uv run --only-group=tox tox run -e lint,typing,py,coverage-report
```

### Running Individual Tests

```bash
uv run --only-group=tox tox run -e py -- tests/handlers/external_test.py  # Run specific test file
uv run --only-group=tox tox run -e py -- tests/handlers/external_test.py::test_function_name  # Run specific test
uv run --only-group=tox tox run -e py -- -k "pattern"    # Run tests matching pattern
```

## Architecture

### Request Flow

1. **External requests** arrive at `/turborepo-cache/*` (configured via `config.path_prefix`)
2. **external_router** (`handlers/external.py`) catches all requests with a catch-all route `/{path:path}`
3. **handle_proxy_request** performs the core proxy logic:
   - Strips the path prefix to get the backend path
   - Filters hop-by-hop headers (Connection, Transfer-Encoding, Host, etc.)
   - Adds static Bearer token authentication for the backend cache
   - Streams the request body to the backend
   - Streams the response back to the client without modification
4. **Backend cache** (Ductors Turborepo cache) at `config.cache_url` receives the proxied request

### Key Components

**Configuration** (`config.py`):

- Environment-based settings with `TURBOREPO_CACHE_PROXY_` prefix
- `cache_url`: Backend Turborepo cache URL
- `cache_token`: Static Bearer token for backend authentication
- `path_prefix`: External URL prefix (default: `/turborepo-cache`)
- `slack_webhook`: Optional Slack alerting for errors

**Dependencies** (`dependencies/proxyclient.py`):

- `ProxyClientDependency`: Provides a specialized `httpx.AsyncClient` for proxying
- Configured with no read/write timeouts (handles large artifact uploads/downloads)
- Connection pooling (max 100 connections, 20 keepalive)
- Must be closed in app lifespan hook

**Handlers**:

- `internal_router` (`handlers/internal.py`): Serves `/` for health checks and metadata (not externally visible)
- `external_router` (`handlers/external.py`): Serves `/turborepo-cache/*` for cache operations

**Application** (`main.py`):

- FastAPI app with Safir middleware (XForwardedMiddleware for proxy headers)
- Lifespan management for HTTP client cleanup
- Slack error reporting via SlackRouteErrorHandler (if configured)
- OpenAPI docs at `{path_prefix}/docs`

### Testing

Tests use:

- `pytest` with `pytest-asyncio` for async test support
- `asgi-lifespan` to manage app startup/shutdown in tests
- `respx` for mocking HTTP requests to the backend cache
- `httpx.AsyncClient` with `ASGITransport` for testing the FastAPI app

Test fixtures in `tests/conftest.py`:

- `app`: FastAPI app wrapped in LifespanManager
- `client`: AsyncClient configured to talk to test app

## Technology Stack

- **FastAPI**: Web framework
- **Safir**: Rubin Observatory's FastAPI utilities (logging, middleware, Slack alerts)
- **httpx**: Async HTTP client for proxying
- **Pydantic**: Configuration and data validation
- **uv**: Dependency management and tooling
- **tox**: Test automation
- **Ruff**: Linting and formatting
- **mypy**: Type checking

## Code Style

- Python 3.14 required
- Strict type checking enabled (mypy with strict settings)
- Import sorting via Ruff (isort rules)
- Shared Ruff configuration in `ruff-shared.toml`
- All FastAPI dependencies use `Annotated` type hints
- Structured logging via structlog

## Environment Variables

Set these when running locally (prefix: `TURBOREPO_CACHE_PROXY_`):

- `CACHE_URL`: Backend Turborepo cache URL (required)
- `CACHE_TOKEN`: Static Bearer token for backend (required)
- `PATH_PREFIX`: URL prefix (default: `/turborepo-cache`)
- `LOG_LEVEL`: Logging level (default: INFO)
- `LOG_PROFILE`: Logging profile (default: development)
- `SLACK_WEBHOOK`: Optional Slack webhook for alerts
