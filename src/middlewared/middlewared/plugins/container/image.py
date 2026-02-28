from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerImageQueryRegistryArgs, ContainerImageQueryRegistryResult, ContainerImageQueryRegistryResultImage,
    ContainerImageQueryRegistryResultImageVersion,
)
from middlewared.service import job, private, Service

from .query_pull_images import query_registry_images, pull


if typing.TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


class ContainerImageService(Service):

    class Config:
        cli_namespace = 'service.container.image'
        namespace = 'container.image'
        role_prefix = 'CONTAINER_IMAGE'
        generic = True

    @api_method(
        ContainerImageQueryRegistryArgs, ContainerImageQueryRegistryResult, roles=['CONTAINER_IMAGE_READ'],
        check_annotations=True,
    )
    def query_registry(self) -> list[ContainerImageQueryRegistryResultImage]:
        """
        Query images available in the images registry.
        """
        products = query_registry_images(self.context)['products']

        return [
            ContainerImageQueryRegistryResultImage(
                name=name,
                versions=[
                    ContainerImageQueryRegistryResultImageVersion(version=version)
                    for version in product["versions"].keys()
                ],
            )
            for name, product in products.items()
        ]

    @job()
    @private
    def pull(self, job: Job, pool: str, image: dict[str, typing.Any]) -> str:
        """
        Pull image.
        """
        return pull(self.context, job, pool, image)


async def setup(middleware: Middleware) -> None:
    await middleware.call('network.general.register_activity', 'container', 'Container images registry')
