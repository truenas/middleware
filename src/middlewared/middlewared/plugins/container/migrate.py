import ipaddress
import os
import yaml

from truenas_pylibvirt.utils.usb import USBInventory

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.base.handler.accept import validate_model
from middlewared.api.current import (
    ContainerMigrateArgs, ContainerMigrateResult,
    ContainerUSBDevice,
    ZFSResourceQuery,
)
from middlewared.service import CallError, job, private, Service
from middlewared.plugins.pool_.utils import UpdateImplArgs
from middlewared.utils.usb import normalize_usb_id

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
        all_nic_choices = set(nic_choices['BRIDGE']) | set(nic_choices['MACVLAN'])
        gpu_choices = await self.middleware.call("container.device.gpu_choices")
        usb_inventory = await self.middleware.run_in_thread(USBInventory.collect)
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
                    if device_data.get("parent") not in all_nic_choices:
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
                        "mac": manifest["config"].get(f"volatile.{device_name}.hwaddr")
                    }
                elif dtype == "usb":
                    if (bus_num := device_data.get("busnum")) and (devnum := device_data.get("devnum")):
                        # incus identified the device by an enumeration counter the kernel hands
                        # out afresh on every replug. This is the only moment it can be turned
                        # into a stable identity: the device is still plugged in and this is the
                        # machine that owns it.
                        info = usb_inventory.by_bus_devnum(str(bus_num), str(devnum))
                        if info is None:
                            await job.logs_fd_write((
                                f"Skipping migration of USB device {device_name!r} for container "
                                f"{container_name!r}: no USB device is currently connected at bus {bus_num} "
                                f"address {devnum}, so its physical port cannot be determined. Plug the "
                                f"device in and re-add it from the container's USB devices page.\n"
                            ).encode())
                            continue

                        device_payload = {
                            "dtype": "USB",
                            "port": info.port,
                            "usb": None,
                        }
                    elif (vendor_id := device_data.get("vendorid")) and (product_id := device_data.get("productid")):
                        device_payload = {
                            "dtype": "USB",
                            "usb": {
                                "vendor_id": normalize_usb_id(str(vendor_id)),
                                "product_id": normalize_usb_id(str(product_id)),
                            },
                            "port": None,
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
                    if dtype == "usb":
                        # The rows go in through datastore.insert, which does not validate, so a
                        # payload the API cannot read back would only surface later as a broken
                        # device the user cannot even see.
                        try:
                            validate_model(ContainerUSBDevice, device_payload)
                        except Exception as e:
                            await job.logs_fd_write((
                                f"Skipping migration of USB device {device_name!r} for container "
                                f"{container_name!r} because the migrated configuration is not valid: "
                                f"{e!r}.\n"
                            ).encode())
                            continue

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

    @private
    async def maybe_migrate_legacy(self):
        """Check for legacy incus containers and auto-migrate if found.

        Called on system ready. If virt_global.pool is set, legacy containers
        exist and need migration. On success, sets preferred_pool and clears
        virt_global.pool so migration does not re-trigger on next boot.
        """
        legacy_config = await self.middleware.call("datastore.query", "virt.global")
        if not legacy_config or legacy_config[0]["pool"] is None:
            return

        legacy_config = legacy_config[0]
        self.logger.info("Legacy incus container configuration found, starting migration")
        try:
            migration_job = await self.middleware.call("container.migrate")
            await migration_job.wait(raise_error=True)
        except Exception:
            self.logger.error("Legacy container migration failed", exc_info=True)
            return

        container_config = await self.middleware.call("lxc.config")
        updates = {}
        if container_config["preferred_pool"] is None and legacy_config["pool"]:
            updates["preferred_pool"] = legacy_config["pool"]

        for col in ("bridge", "v4_network", "v6_network"):
            if not legacy_config.get(col):
                continue

            value = legacy_config[col]
            if col in ("v4_network", "v6_network"):
                try:
                    value = str(ipaddress.ip_network(value, strict=False))
                except (ValueError, TypeError):
                    continue

            updates[col] = value

        if updates:
            await self.middleware.call(
                "datastore.update", "container.config", container_config["id"], updates,
            )

        await self.middleware.call(
            "datastore.update", "virt.global", legacy_config["id"],
            {"pool": None},
        )
        self.logger.info("Legacy container migration completed")

    @api_method(ContainerMigrateArgs, ContainerMigrateResult, roles=["CONTAINER_WRITE"])
    @job(lock="container.migrate", logs=True)
    async def migrate(self, job):
        """Migrate incus containers to new API."""

        legacy_configuration = await self.middleware.call("datastore.query", "virt.global")
        if not legacy_configuration or legacy_configuration[0]["pool"] is None:
            raise CallError("Legacy containers configuration pool is not set.")
        pool = legacy_configuration[0]["pool"]

        storage_pools = {pool} | set(filter(bool, (legacy_configuration[0]["storage_pools"] or "").split()))
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
                job.logs_fd.write(
                    f"Skipping dataset {dataset['name']} during migration (not a container dataset)".encode(),
                )
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
                    UpdateImplArgs(
                        name=dataset["name"],
                        zprops={"canmount": "on"},
                        iprops={"mountpoint"},
                    )
                )
                self.call_sync2(self.s.zfs.resource.mount, dataset["name"])

                try:
                    with open(f"/mnt/{dataset['name']}/backup.yaml") as f:
                        manifest = yaml.safe_load(f.read())
                except Exception:
                    job.logs_fd.write(
                        f"Failed to read backup.yaml for container {name!r}, skipping.\n".encode()
                    )
                    continue

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
                        'cpuset': config.get('limits.cpu', None),
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
