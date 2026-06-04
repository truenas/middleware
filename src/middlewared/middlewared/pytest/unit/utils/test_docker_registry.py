import pytest

from middlewared.utils.docker_registry import DEFAULT_DOCKER_REGISTRY, normalize_registry_authority


@pytest.mark.parametrize(
    "uri_or_reference,expected",
    [
        # Non-Hub registries collapse to a bare authority regardless of how typed.
        # This is the original regression: a stored "https://ghcr.io/" URI must reduce
        # to the same value as the "ghcr.io" registry an image reference parses to.
        ("https://ghcr.io/", "ghcr.io"),
        ("ghcr.io", "ghcr.io"),
        ("https://ghcr.io/v2/", "ghcr.io"),
        ("quay.io", "quay.io"),
        # Every Docker Hub alias maps to the registry docker.io images normalize to.
        ("docker.io", DEFAULT_DOCKER_REGISTRY),
        ("index.docker.io", DEFAULT_DOCKER_REGISTRY),
        ("https://index.docker.io/v1/", DEFAULT_DOCKER_REGISTRY),
        ("registry-1.docker.io", DEFAULT_DOCKER_REGISTRY),
        # Ports are part of the authority and must be preserved.
        ("myregistry:5000", "myregistry:5000"),
        ("https://myregistry:5000/", "myregistry:5000"),
    ],
)
def test__normalize_registry_authority(uri_or_reference, expected):
    assert normalize_registry_authority(uri_or_reference) == expected


def test__normalize_registry_authority_is_idempotent():
    for value in ("ghcr.io", "https://ghcr.io/", "docker.io", "myregistry:5000"):
        once = normalize_registry_authority(value)
        assert normalize_registry_authority(once) == once
