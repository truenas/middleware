import os
import yaml

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    ContainerMigrateArgs, ContainerMigrateResult,
    ZFSResourceQuery,
)
from middlewared.service import CallError, job, private, Service
from middlewared.plugins.pool_.utils import UpdateImplArgs

from .utils import container_dataset


class VirtGlobalModel(sa.Model):
    """Legacy virt_global table model for migration purposes."""
    __tablename__ = 'virt_global'

    id = sa.Column(sa.Integer(), primary_key=True)
    pool = sa.Column(sa.String(120), nullable=True)
    storage_pools = sa.Column(sa.Text(), nullable=True)
    bridge = sa.Column(sa.String(120), nullable=True)
    v4_network = sa.Column(sa.String(120), nullable=True)
    v6_network = sa.Column(sa.String(120), nullable=True)


class ContainerService(Service):

    @private
    async def migrate_devices(self, job, manifest, container_instance):
        devices = manifest["devices"]
        container_name = container_instance["name"]
        nic_choices = await self.middleware.call("container.device.nic_attach_choices")
        gpu_choices = await self.middleware.call("container.device.gpu_choices")
        for device_name, device_data in devices.items():
            dtype = None
            try:
                device_payload = None
                dtype = device_data.get("type")
                if dtype == "disk":
                    src = device_data.get("source", "")
                    if src.startswith("/mnt") is False:
                        await job.logs_fd_write((
                            f"Skipping migrating {device_name!r} disk device for {container_name!r} because "
                            f"source does not start with /mnt/ (is {src!r} instead)\n"
                        ).encode())
                        continue

                    device_payload = {
                        "dtype": "FILESYSTEM",
                        "source": src,
                        "target": device_data["path"],
                    }
                elif dtype == "nic":
                    if device_data.get("parent") not in nic_choices:
                        await job.logs_fd_write((
                            f"Skipping migrating {device_name!r} NIC device for {container_name!r} because "
                            f"{device_data.get('parent')!r} is not a valid NIC\n"
                        ).encode())
                        continue

                    device_payload = {
                        "dtype": "NIC",
                        "nic_attach": device_data["parent"],
                        "type": "VIRTIO",
                        "trust_guest_rx_filters": False,
                        "mac": manifest["config"].get(f"volatile.{device_data['parent']}.hwaddr")
                    }
                elif dtype == "usb":
                    if (bus_num := device_data.get("busnum")) and (devnum := device_data.get("devnum")):
                        device_payload = {
                            "dtype": "USB",
                            "device": f"usb_{bus_num}_{devnum}",
                            "usb": None,
                        }
                    elif (vendor_id := device_data.get("vendorid")) and (product_id := device_data.get("productid")):
                        device_payload = {
                            "dtype": "USB",
                            "usb": {"vendor_id": f"0x{vendor_id}", "product_id": f"0x{product_id}"},
                            "device": None
                        }
                    else:
                        await job.logs_fd_write((
                            f"Skipping migration of USB device {device_name!r} for container {container_name!r} "
                            "because the USB data is invalid or incomplete\n"
                        ).encode())
                        continue

                elif dtype == "gpu":
                    pci_address = device_data.get("pci")
                    if pci_address not in gpu_choices:
                        await job.logs_fd_write((
                            f"Skipping migrating {device_name!r} GPU device for {container_name!r} because "
                            f"{pci_address!r} is not a valid PCI address for a GPU device\n"
                        ).encode())
                        continue

                    device_payload = {
                        "dtype": "GPU",
                        "gpu_type": gpu_choices[pci_address],
                        "pci_address": pci_address,
                    }
                else:
                    await job.logs_fd_write((
                        f"Skipping migrating {device_name!r} device for {container_name!r} because "
                        f"unhandled device type {dtype!r} found\n"
                    ).encode())
            except Exception as e:
                await job.logs_fd_write(
                    f"Unable to migrate {device_name!r} {dtype} device for {container_name!r}: {e!r}.\n".encode()
                )
                continue
            else:
                if device_payload:
                    try:
                        await self.middleware.call(
                            "datastore.insert", "container.device", {
                                "attributes": device_payload,
                                "container_id": container_instance["id"],
                            }
                        )
                    except Exception as e:
                        # Should not happen but better safe than sorry
                        await job.logs_fd_write(
                            f"Unable to create container device for {device_name!r} {dtype} incus "
                            f"device: {e!r}.\n".encode()
                        )

    @api_method(ContainerMigrateArgs, ContainerMigrateResult, roles=["CONTAINER_WRITE"])
    @job(lock="container.migrate", logs=True)
    async def migrate(self, job):
        """Migrate incus containers to new API."""

        legacy_configuration = await self.middleware.call("datastore.config", "virt.global")
        pool = legacy_configuration["pool"]
        if pool is None:
            raise CallError("Legacy containers configuration pool is not set.")

        storage_pools = {pool} | set(filter(bool, (legacy_configuration["storage_pools"] or "").split()))
        existing_containers = {
            container["name"]: container for container in await self.middleware.call("container.query")
        }
        for storage_pool in storage_pools:
            await self.middleware.call("container.migrate_specific_pool", job, storage_pool, existing_containers)

    @private
    def migrate_specific_pool(self, job, pool, existing_containers):
        processed_parents_mountpoints = False
        datasets = self.call_sync2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(
                paths=[f"{pool}/.ix-virt/containers"],
                get_children=True,
                properties=None
            )
        )
        if datasets:
            self.middleware.call_sync("container.ensure_datasets", pool)

        for dataset in datasets:
            if dataset["type"] != "FILESYSTEM":
                continue

            split = dataset["name"].split("/")
            if len(split) != 4:
                continue

            name = split[-1]
            if name in existing_containers:
                job.logs_fd.write((
                    f"Migration skipped for container {name!r} because a container with the same name "
                    f"already exists\n"
                ).encode())
                continue

            dst_dataset = os.path.join(container_dataset(pool), f"containers/{name}")
            try:
                if not processed_parents_mountpoints:
                    for ds in (f"{pool}/.ix-virt", f"{pool}/.ix-virt/containers"):
                        self.middleware.call_sync(
                            "pool.dataset.update_impl",
                            UpdateImplArgs(
                                name=ds,
                                zprops={"readonly": "off"},
                                iprops={"mountpoint"}
                            )
                        )
                    processed_parents_mountpoints = True

                self.middleware.call_sync(
                    "pool.dataset.update_impl",
                    UpdateImplArgs(name=dataset["name"], iprops={"mountpoint"})
                )
                self.call_sync2(self.s.zfs.resource.mount, dataset["name"])

                with open(f"/mnt/{dataset['name']}/backup.yaml") as f:
                    manifest = yaml.safe_load(f.read())

                config = manifest["container"]["config"]

                # Move rootfs contents to parent dataset for compatibility with current implementation
                rootfs_path = f"/mnt/{dataset['name']}/rootfs"
                parent_path = f"/mnt/{dataset['name']}"
                with os.scandir(rootfs_path) as entries:
                    for entry in entries:
                        os.rename(entry.path, os.path.join(parent_path, entry.name))

                rootfs_stats = os.stat(rootfs_path)
                os.chmod(parent_path, rootfs_stats.st_mode)
                os.chown(parent_path, rootfs_stats.st_uid, rootfs_stats.st_gid)
                os.rmdir(rootfs_path)

                self.call_sync2(self.s.zfs.resource.rename, dataset["name"], dst_dataset)

                container_instance = self.middleware.call_sync(
                    "container.create_with_dataset",
                    {
                        "name": name,
                        "autostart": config.get("user.autostart") == "true",
                        "dataset": dst_dataset,
                        "init": "/sbin/init",
                    },
                )
                self.middleware.call_sync(
                    "container.migrate_devices", job, manifest["container"], container_instance
                )
            except Exception as e:
                self.logger.error("Unable to migrate container %r", name, exc_info=True)
                job.logs_fd.write(f"Unable to migrate container {name!r}: {e!r}.\n".encode())
            else:
                job.logs_fd.write(f"Successfully migrated container {name!r}.\n".encode())
