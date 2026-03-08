from __future__ import annotations

import typing

from middlewared.api.current import DockerNetworkEntry
from middlewared.service import GenericCRUDService, private

from .docker_network_crud import DockerNetworkServicePart

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('DockerNetworkService',)


class DockerNetworkService(GenericCRUDService[DockerNetworkEntry]):

    class Config:
        cli_namespace = 'docker.network'
        entry = DockerNetworkEntry
        namespace = 'docker.network'
        role_prefix = 'DOCKER'

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = DockerNetworkServicePart(self.context)

    @private
    async def interfaces_mapping(self) -> list[str]:
        return await self._svc_part.interfaces_mapping()
