from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerImageQueryRegistryArgs,
    ContainerImageQueryRegistryResult,
    ContainerImageQueryRegistryResultImage,
    ContainerImageQueryRegistryResultImageVersion,
)
from middlewared.service import Service, job, private

from .query_pull_images import pull, query_registry_images

if typing.TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


class ContainerImageService(Service):

    class Config:
        cli_namespace = "service.container.image"
        namespace = "container.image"
        role_prefix = "CONTAINER_IMAGE"
        generic = True

    @api_method(
        ContainerImageQueryRegistryArgs, ContainerImageQueryRegistryResult, roles=["CONTAINER_IMAGE_READ"],
        check_annotations=True,
    )
    def query_registry(self) -> list[ContainerImageQueryRegistryResultImage]:
        """
        Query images available in the images registry.
        """
        products = query_registry_images(self.context)["products"]

        result = []
        for name, product in products.items():
            # Only include versions that have a root.tar.xz (container rootfs).
            # VM-only images (desktop, freebsd, etc.) only ship disk.qcow2.
            versions = []
            for version, vdata in product["versions"].items():
                if "root.tar.xz" in vdata.get("items", {}):
                    versions.append(ContainerImageQueryRegistryResultImageVersion(version=version))

            if versions:
                result.append(ContainerImageQueryRegistryResultImage(name=name, versions=versions))

        return result

    @job()
    @private
    def pull(self, job: Job, pool: str, image: dict[str, typing.Any]) -> str:
        """
        Pull image.
        """
        return pull(self.context, job, pool, image)


async def setup(middleware: Middleware) -> None:
    await middleware.call("network.general.register_activity", "container", "Container images registry")
