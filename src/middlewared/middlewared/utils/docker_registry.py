from __future__ import annotations

# Registry containerd/normalize_reference maps any docker.io image to, and the
# canonical authority every Docker Hub alias collapses to.
DEFAULT_DOCKER_REGISTRY = "registry-1.docker.io"

# Docker Hub answers under several interchangeable hostnames; they all refer to the
# same registry and must be treated as one when matching stored credentials.
DOCKER_HUB_REGISTRY_ALIASES = frozenset(
    {
        "docker.io",
        "index.docker.io",
        "registry-1.docker.io",
    }
)


def normalize_registry_authority(uri_or_reference: str) -> str:
    """Reduce a registry URI or image-reference registry to a canonical authority.

    The registry portion of an image reference is a bare hostname (``ghcr.io``,
    ``registry-1.docker.io``), but users can enter the URI in `app.registry` in
    several equivalent forms (``https://ghcr.io/``, ``ghcr.io``,
    ``https://index.docker.io/v1/``, etc). This strips scheme, path and trailing
    slash down to ``host[:port]`` and collapses every Docker Hub alias to
    ``DEFAULT_DOCKER_REGISTRY`` so credentials stored under any Hub form match
    images that get normalized to registry-1.docker.io.
    """
    host = uri_or_reference
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.rstrip("/").split("/", 1)[0]
    if host in DOCKER_HUB_REGISTRY_ALIASES:
        return DEFAULT_DOCKER_REGISTRY
    return host
