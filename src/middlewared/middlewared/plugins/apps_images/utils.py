from __future__ import annotations

import re
from typing import Any

from middlewared.api.current import AppRegistryEntry
from middlewared.service import CallError
from middlewared.utils.docker_registry import DEFAULT_DOCKER_REGISTRY, normalize_registry_authority

# Default values
DEFAULT_DOCKER_REPO = "library"
DEFAULT_DOCKER_TAG = "latest"
DOCKER_CONTENT_DIGEST_HEADER = "Docker-Content-Digest"

# Taken from OCI: https://github.com/opencontainers/go-digest/blob/master/digest.go#L63
DIGEST_RE = r"[a-z0-9]+(?:[.+_-])*:[a-zA-Z0-9=_-]+"


DOCKER_AUTH_HEADER = "WWW-Authenticate"
DOCKER_AUTH_URL = "https://auth.docker.io/token"
DOCKER_AUTH_SERVICE = "registry.docker.io"
DOCKER_MANIFEST_OCI_V1 = "application/vnd.oci.image.index.v1+json"
DOCKER_MANIFEST_SCHEMA_V1 = "application/vnd.docker.distribution.manifest.v1+json"
DOCKER_MANIFEST_SCHEMA_V2 = "application/vnd.docker.distribution.manifest.v2+json"
DOCKER_MANIFEST_LIST_SCHEMA_V2 = "application/vnd.docker.distribution.manifest.list.v2+json"
DOCKER_RATELIMIT_URL = "https://registry-1.docker.io/v2/ratelimitpreview/test/manifests/latest"


def parse_digest_from_schema(response: dict[str, Any]) -> list[str]:
    """
    Parses out the digest according to schemas specs:
    https://docs.docker.com/registry/spec/manifest-v2-1/
    """
    media_type = response["response"]["mediaType"]
    if media_type == DOCKER_MANIFEST_SCHEMA_V2:
        digest_value = response["response"]["config"]["digest"]
        return [digest_value] if isinstance(digest_value, str) else digest_value
    elif media_type == DOCKER_MANIFEST_LIST_SCHEMA_V2:
        if manifests := response["response"]["manifests"]:
            return [digest["digest"] for digest in manifests]
    return []


def parse_auth_header(header: str) -> dict[str, str]:
    """
    Parses a ``WWW-Authenticate`` challenge header.

    A Bearer/token-auth challenge, e.g.:
    'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="redis:pull"'

    returns:
        {
            'scheme': 'bearer',
            'auth_url': 'https://ghcr.io/token',
            'service': 'ghcr.io',
            'scope': 'redis:pull'
        }

    An HTTP Basic challenge (e.g. a private registry using htpasswd auth):
    'Basic realm="example.com"'

    returns:
        {
            'scheme': 'basic',
            'auth_url': 'example.com'
        }

    Basic challenges carry no token endpoint or ``scope`` (the parsed ``realm`` is
    unused), so callers must branch on ``scheme`` rather than assuming a
    token-exchange flow. Optional whitespace around the comma-separated parameters
    is tolerated (RFC 7235).
    """
    adapter = {
        "realm": "auth_url",
        "service": "service",
        "scope": "scope",
    }
    results: dict[str, str] = {}
    # Split the scheme from its parameters on the first run of whitespace so a tab or
    # multiple spaces between them is tolerated (RFC 7235 uses SP, but be lenient).
    tokens = header.strip().split(maxsplit=1)
    if not tokens:
        return results
    results['scheme'] = tokens[0].lower()
    params = tokens[1] if len(tokens) > 1 else ''
    for part in params.split(','):
        # partition on the first '=' so values that themselves contain '=' survive.
        key, sep, value = part.strip().partition('=')
        if sep and key in adapter:
            results[adapter[key]] = value.strip().strip('"')
    return results


def normalize_reference(reference: str) -> dict[str, Any]:
    """
    Parses the reference for image, tag and repository.

    Most of the logic has been used from docker engine to make sure we follow the same rules/practices
    for normalising the image name / tag
    """
    # This needs to be done as containerd automatically adds docker.io as a registery which can't be queried by us
    # when checking for update alerts as registry-1.docker.io is the one used to actually query that information
    reference = reference.removeprefix("docker.io/")
    registry_idx = reference.find("/")
    if registry_idx == -1 or (
        not any(c in reference[:registry_idx] for c in (".", ":")) and reference[:registry_idx] != "localhost"
    ):
        registry, tagged_image = DEFAULT_DOCKER_REGISTRY, reference
    else:
        registry, tagged_image = reference[:registry_idx], reference[registry_idx + 1 :]

    if "/" not in tagged_image:
        tagged_image = f"{DEFAULT_DOCKER_REPO}/{tagged_image}"

    # if image is not tagged, use default value.
    if ":" not in tagged_image:
        tagged_image += f":{DEFAULT_DOCKER_TAG}"

    # At this point, tag should be included already – we just need to see whether this
    # tag is named or digested and respond accordingly.
    ref_is_digest = False
    if "@" in tagged_image:
        matches = re.findall(DIGEST_RE, tagged_image)
        if not matches:
            raise CallError(f"Invalid reference format: {tagged_image}")

        tag = matches[-1]
        tag_pos = tagged_image.find(tag)
        image = tagged_image[: tag_pos - 1].rsplit(":", 1)[0]
        sep = "@"
        ref_is_digest = True
    elif ":" in tagged_image:
        image, tag = tagged_image.rsplit(":", 1)
        sep = ":"
    else:
        # Unreachable: we added `:<tag>` above if no colon was present.
        raise CallError(f"Invalid reference format: {tagged_image}")

    return {
        "reference": reference,
        "image": image,
        "tag": tag,
        "registry": registry,
        "complete_tag": f"{registry}/{image}{sep}{tag}",
        "reference_is_digest": ref_is_digest,
    }


def parse_tags(references: list[str]) -> list[dict[str, Any]]:
    return [normalize_reference(reference=reference) for reference in references]


def normalize_docker_limits_header(headers: dict[str, Any]) -> dict[str, Any]:
    if not all(limit_key in headers for limit_key in ["ratelimit-limit", "ratelimit-remaining"]):
        return {"error": "Unable to retrieve rate limit information from registry"}

    total_pull_limit, total_time_limit = headers["ratelimit-limit"].split(";w=")
    remaining_pull_limit, remaining_time_limit = headers["ratelimit-remaining"].split(";w=")

    return {
        "total_pull_limit": int(total_pull_limit),
        "total_time_limit_in_secs": int(total_time_limit),
        "remaining_pull_limit": int(remaining_pull_limit),
        "remaining_time_limit_in_secs": int(remaining_time_limit),
        "error": None,
    }


def get_normalized_auth_config(
    registries: list[AppRegistryEntry],
    image_tag: str,
) -> dict[str, Any]:
    """Return stored credentials for the registry hosting ``image_tag``, or {}."""
    user_wants_registry = normalize_reference(image_tag)["registry"]
    target = normalize_registry_authority(user_wants_registry)
    for entry in registries:
        if normalize_registry_authority(entry.uri) == target:
            return {
                "registry_uri": user_wants_registry,
                "username": entry.username.get_secret_value(),
                "password": entry.password.get_secret_value(),
            }
    return {}
