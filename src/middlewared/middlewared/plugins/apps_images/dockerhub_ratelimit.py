from __future__ import annotations

from middlewared.api.current import AppImageDockerhubRateLimitInfo
from middlewared.service import ServiceContext

from .client import ContainerRegistryClientMixin
from .utils import normalize_docker_limits_header


async def get_dockerhub_rate_limit(context: ServiceContext) -> AppImageDockerhubRateLimitInfo:
    """
    Return Docker Hub rate-limit info. If credentials are configured in `app.registry` they are
    used for the authenticated preview token; otherwise the anonymous limits are reported.

    See https://docs.docker.com/docker-hub/download-rate-limit/ for details.
    """
    auth: dict[str, str] | None = None
    creds = await context.call2(
        context.s.app.registry.query,
        [["uri", "=", "https://index.docker.io/v1/"]],
    )
    if creds:
        auth = {
            "login": creds[0].username.get_secret_value(),
            "password": creds[0].password.get_secret_value(),
        }

    limits_header = await ContainerRegistryClientMixin().get_docker_hub_rate_limit_preview(auth)

    response_obj = limits_header.get("response_obj")
    if response_obj is not None and hasattr(response_obj, "headers"):
        return AppImageDockerhubRateLimitInfo.model_validate(normalize_docker_limits_header(response_obj.headers))

    return AppImageDockerhubRateLimitInfo(
        error="Unable to retrieve rate limit information from registry",
    )
