import yaml

import humanfriendly

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerMigrateArgs, ContainerMigrateResult,
)
from middlewared.service import CallError, job, private, Service


class ContainerService(Service):
    @api_method(ContainerMigrateArgs, ContainerMigrateResult, roles=["CONTAINER_WRITE"])
    @job(lock="container.migrate", logs=True)
    async def migrate(self, job):
        """Migrate incus containers to new API."""

        legacy_configuration = await self.middleware.call("datastore.config", "virt.global")
        pool = legacy_configuration["pool"]
        if pool is None:
            raise CallError("Legacy containers configuration pool is not set.")

        processed_parents_mountpoints = False
        for dataset in await self.middleware.call(
            "zfs.resource.query_impl",
            {
                "paths": [f"{pool}/.ix-virt/containers"],
                "get_children": True,
                "properties": None
            }
        ):
            if dataset["type"] != "FILESYSTEM":
                continue

            split = dataset["name"].split("/")
            if len(split) != 4:
                continue

            name = split[-1]
            try:
                if not processed_parents_mountpoints:
                    await self.middleware.call("zfs.dataset.update", f"{pool}/.ix-virt", {
                        "properties": {
                            "mountpoint": {"source": "INHERIT"},
                            "readonly": {"value": "off"},
                        }
                    })
                    await self.middleware.call("zfs.dataset.update", f"{pool}/.ix-virt/containers", {
                        "properties": {
                            "mountpoint": {"source": "INHERIT"},
                            "readonly": {"value": "off"},
                        }
                    })
                    processed_parents_mountpoints = True

                await self.middleware.call("zfs.dataset.update", dataset["name"], {
                    "properties": {
                        "mountpoint": {"source": "INHERIT"},
                    }
                })
                await self.middleware.call("zfs.dataset.mount", dataset["name"])

                with open(f"/mnt/{dataset['name']}/backup.yaml") as f:
                    manifest = yaml.safe_load(f.read())

                config = manifest["container"]["config"]

                try:
                    memory = int(
                        humanfriendly.parse_size(config["limits.memory"]) / (1024 ** 2) + 0.5
                    )
                except (KeyError, humanfriendly.InvalidSize):
                    memory = None

                await self.middleware.call(
                    "container.create_with_dataset",
                    {
                        "name": name,
                        "memory": memory,
                        "autostart": config.get("user.autostart") == "true",
                        "dataset": f"{dataset['name']}/rootfs",
                        "init": "/sbin/init",
                    },
                )
            except Exception as e:
                self.logger.error("Unable to migrate container %r", name, exc_info=True)
                await job.logs_fd_write(
                    f"Unable to migrate container {name!r}: {e!r}.\n".encode("utf-8", "ignore")
                )
            else:
                await job.logs_fd_write(
                    f"Successfully migrated container {name!r}.\n".encode("utf-8", "ignore")
                )
