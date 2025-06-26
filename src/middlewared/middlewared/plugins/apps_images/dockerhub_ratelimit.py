from middlewared.api import api_method
from middlewared.api.current import ContainerImagesDockerhubRateLimitArgs, ContainerImagesDockerhubRateLimitResult
from middlewared.service import Service

from .client import ContainerRegistryClientMixin
from .utils import normalize_docker_limits_header


class ContainerImagesService(Service):

    class Config:
        namespace = 'app.image'

    @api_method(ContainerImagesDockerhubRateLimitArgs, ContainerImagesDockerhubRateLimitResult, roles=['APPS_READ'])
    async def dockerhub_rate_limit(self):
        """
        Returns the current rate limit information for Docker Hub registry.

        Please refer to https://docs.docker.com/docker-hub/download-rate-limit/ for more information.
        """
        auth = None
        if creds := (await self.middleware.call('app.registry.query', [['uri', '=', 'https://index.docker.io/v1/']])):
            auth = {'login': creds[0]['username'], 'password': creds[0]['password']}

        limits_header = await ContainerRegistryClientMixin().get_docker_hub_rate_limit_preview(auth)

        if limits_header.get('response_obj') and hasattr(limits_header['response_obj'], 'headers'):
            return normalize_docker_limits_header(limits_header['response_obj'].headers)

        return {
            'error': 'Unable to retrieve rate limit information from registry',
        }
