import pytest

from middlewared.plugins.apps_images.utils import parse_auth_header


@pytest.mark.parametrize(
    "header,expected",
    [
        # Bearer/token-auth challenge (Docker Hub, ghcr.io, ...) advertises a scope.
        (
            'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="redis:pull"',
            {
                "scheme": "bearer",
                "auth_url": "https://ghcr.io/token",
                "service": "ghcr.io",
                "scope": "redis:pull",
            },
        ),
        # HTTP Basic challenge (private registry using htpasswd auth): no token endpoint
        # and no scope. Regression for NAS-141553 - the scheme must be surfaced so the
        # caller does not treat this as a Bearer flow (which crashed on the missing
        # `scope` argument to `_get_token`).
        ('Basic realm="example.com"', {"scheme": "basic", "auth_url": "example.com"}),
        # The auth scheme is case-insensitive per RFC 7235.
        ('BASIC realm="example.com"', {"scheme": "basic", "auth_url": "example.com"}),
        # A bare scheme with no parameters still reports the scheme.
        ("Basic", {"scheme": "basic"}),
        # An empty header degrades gracefully.
        ("", {}),
    ],
)
def test__parse_auth_header(header, expected):
    assert parse_auth_header(header) == expected
