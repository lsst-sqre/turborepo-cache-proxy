# turborepo-cache-proxy

Proxy for a Phalanx-hosted Turborepo remote cache that exchanges Gafaelfawr auth for a cache token.

This application proxies the [Turborepo remote cache implemented by Ductors](https://github.com/ductors/turborepo-cache). With this cache deployed in [Phalanx](https://phalanx.lsst.io/), clients can use Gafaelfawr access tokens to authenticate with the cache proxy. The proxy streams the request to the Ductors cache, adding a static Bearer token for authentication.
The proxy also handles rewriting the path so that the cache is externally deployed with a URL prefix, such as `/turborepo-cache/`, while the Ductors cache expects requests at the root path (`/`).

The Turborepo cache is used by [Squareone](https://github.com/lsst-sqre/squareone) to speed up CI by caching build and test artifacts centrally across developer and CI environments.
