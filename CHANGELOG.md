# Change log

turborepo-cache-proxy is versioned with [semver](https://semver.org/).
Dependencies are updated to the latest available version during each release, and aren't noted here.

Find changes for the upcoming release in the project's [changelog.d directory](https://github.com/lsst-sqre/turborepo-cache-proxy/tree/main/changelog.d/).

<!-- scriv-insert-here -->

<a id='changelog-1.0.3'></a>
## 1.0.3 (2026-07-20)

### Other changes

- Update pinned dependencies and pre-commit hooks.

<a id='changelog-1.0.2'></a>
## 1.0.2 (2026-06-15)

### Bug fixes

- Fix the container failing to start with an `exec .../uvicorn: permission denied` (or `no such file or directory`) error when running as a non-root user, as it does under the Phalanx `securityContext`. The 1.0.1 base image bump to Python 3.14 left the project still pinned to Python 3.13, so `uv` built the virtualenv against a downloaded interpreter under `/root` that the runtime image never copies, leaving the interpreter symlink dangling. The project now targets Python 3.14 to match the base image, so the virtualenv uses the system interpreter that is present in the runtime image.

### Other changes

- Pin the runtime `appuser` to UID/GID 1000 (matching the Phalanx `securityContext`) and copy the virtualenv with `--chown=appuser:appuser` so it is owned by the user the container runs as.

<a id='changelog-1.0.1'></a>
## 1.0.1 (2026-06-12)

### Other changes

- Update the Docker base image to Python 3.14.

<a id='changelog-1.0.0'></a>
## 1.0.0 (2025-10-23)

### New features

- Initial implementation of the Turborepo cache proxy server, now working in the Roundtable environment for internal Rubin Observatory use.
