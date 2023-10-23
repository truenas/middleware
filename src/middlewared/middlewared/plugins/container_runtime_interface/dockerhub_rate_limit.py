from middlewared.schema import Dict, Int, returns, Str
from middlewared.service import accepts, Service

from .client import CRIClientMixin
from .utils import normalize_docker_limits_header


class ContainerImagesService(Service):

    class Config:
        namespace = 'container.image'

    @accepts()
    @returns(Dict(
        Int('total_pull_limit', null=True),
        Int('total_time_limit_in_secs', null=True),
        Int('remaining_pull_limit', null=True),
        Int('remaining_time_limit_in_secs', null=True),
        Str('error', null=True),
    ))
    async def dockerhub_rate_limit(self):
        """
        Returns the current rate limit information for Docker Hub registry.
        """
        limits_header = await CRIClientMixin().get_docker_hub_rate_limit_preview()

        if limits_header.get('response_obj') and hasattr(limits_header['response_obj'], 'headers'):
            return normalize_docker_limits_header(limits_header['response_obj'].headers)

        return {
            'error': 'Unable to retrieve rate limit information from registry',
        }
