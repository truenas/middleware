from middlewared.schema import Dict, Int, returns, Str
from middlewared.service import accepts, Service

from .client import ContainerRegistryClientMixin
from .utils import normalize_docker_limits_header


class ContainerImagesService(Service):

    class Config:
        namespace = 'app.image'

    @accepts(roles=['APPS_READ'])
    @returns(Dict(
        Int('total_pull_limit', null=True, description='Total pull limit for Docker Hub registry'),
        Int(
            'total_time_limit_in_secs', null=True,
            description='Total time limit in seconds for Docker Hub registry before the limit renews'
        ),
        Int('remaining_pull_limit', null=True, description='Remaining pull limit for Docker Hub registry'),
        Int(
            'remaining_time_limit_in_secs', null=True,
            description='Remaining time limit in seconds for Docker Hub registry for the '
                        'current pull limit to be renewed'
        ),
        Str('error', null=True),
    ))
    async def dockerhub_rate_limit(self):
        """
        Returns the current rate limit information for Docker Hub registry.

        Please refer to https://docs.docker.com/docker-hub/download-rate-limit/ for more information.
        """
        limits_header = await ContainerRegistryClientMixin().get_docker_hub_rate_limit_preview()

        if limits_header.get('response_obj') and hasattr(limits_header['response_obj'], 'headers'):
            return normalize_docker_limits_header(limits_header['response_obj'].headers)

        return {
            'error': 'Unable to retrieve rate limit information from registry',
        }
