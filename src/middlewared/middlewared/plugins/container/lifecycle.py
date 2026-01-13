import errno

from truenas_pylibvirt import (
    ContainerCapabilitiesPolicy, ContainerDomain, ContainerDomainConfiguration, ContainerIdmapConfiguration,
    ContainerIdmapConfigurationItem, NICDevice, NICDeviceType, Time,
)

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerStartArgs, ContainerStartResult,
    ContainerStopArgs, ContainerStopResult,
)
from middlewared.plugins.account_.constants import CONTAINER_ROOT_UID
from middlewared.service import CallError, job, private, Service

from .utils import container_instance_dataset_mountpoint


IDMAP_COUNT = 65536


class ContainerService(Service):

    @private
    async def start_on_boot(self):
        for container in await self.middleware.call(
            'container.query', [('autostart', '=', True)], {'force_sql_filters': True}
        ):
            try:
                await self.middleware.call('container.start', container['id'])
            except Exception as e:
                self.middleware.logger.error(f'Failed to start {container["name"]!r} container: {e}')

    @private
    async def handle_shutdown(self):
        for container in await self.middleware.call('container.query', [('status.state', '=', 'RUNNING')]):
            await self.middleware.call('container.stop', container['id'], {'force_after_timeout': True})

    @api_method(ContainerStartArgs, ContainerStartResult, roles=["CONTAINER_WRITE"])
    def start(self, id_):
        """Start container."""
        container = self.middleware.call_sync("container.get_instance", id_)

        self.middleware.call_sync("container.configure_bridge")

        self.middleware.libvirt_domains_manager.containers.start(self.pylibvirt_container(container, True))

    @api_method(ContainerStopArgs, ContainerStopResult, roles=["CONTAINER_WRITE"])
    @job(lock=lambda args: f'container_stop_{args[0]}')
    def stop(self, job, id_, options):
        """Stop `id` container."""
        container = self.middleware.call_sync("container.get_instance", id_)
        pylibvirt_container = self.pylibvirt_container(container)

        if options["force"]:
            self.middleware.libvirt_domains_manager.containers.destroy(pylibvirt_container)
            return

        self.middleware.libvirt_domains_manager.containers.shutdown(self.pylibvirt_container(container))
        if (
            options["force_after_timeout"] and
            self.middleware.call_sync("container.get_instance", id_)["status"]["state"] == "RUNNING"
        ):
            self.middleware.libvirt_domains_manager.containers.destroy(pylibvirt_container)

    @private
    def pylibvirt_container(self, container, check_ds=False):
        container = container.copy()
        container.pop("id", None)
        container.pop("status", None)
        container.pop('autostart', None)

        dataset = container.pop("dataset")
        pool = dataset.split("/")[0]
        container["root"] = f"/mnt/{container_instance_dataset_mountpoint(pool, container['name'])}"
        if check_ds:
            datasets = self.call_sync2(self.s.zfs.resource.query_impl, {'paths': [dataset], 'properties': None})
            if not datasets:
                raise CallError(f"Dataset {dataset!r} not found", errno.ENOTDIR)

        container["time"] = Time(container["time"])
        devices = []
        has_nic_device = False
        for device in container.get("devices", []):
            if device["attributes"]["dtype"] == "NIC":
                has_nic_device = True

            devices.append(self.middleware.call_sync("container.device.get_pylibvirt_device", device))

        if not has_nic_device:
            # Add one if one isn't added already
            # TODO: See if this should be desired behaviour
            devices.append(
                NICDevice(
                    type_=NICDeviceType.BRIDGE,
                    source=self.middleware.call_sync("container.bridge_name"),
                    model=None,
                    mac=None,
                    trust_guest_rx_filters=False,
                )
            )

        container["devices"] = devices

        if container["idmap"]:
            match container["idmap"]["type"]:
                case "DEFAULT":
                    item = ContainerIdmapConfigurationItem(
                        target=CONTAINER_ROOT_UID,
                        count=IDMAP_COUNT,
                    )
                case "ISOLATED":
                    item = ContainerIdmapConfigurationItem(
                        target=CONTAINER_ROOT_UID + container["idmap"]["slice"] * IDMAP_COUNT,
                        count=IDMAP_COUNT,
                    )
                case _:
                    raise CallError(f"Unsupported idmap type {container['idmap']['type']!r}")

            container["idmap"] = ContainerIdmapConfiguration(uid=item, gid=item)

        if container["capabilities_policy"]:
            container["capabilities_policy"] = ContainerCapabilitiesPolicy[container["capabilities_policy"]]

        # We add this to configuration because for cpu related attrs, we need them if cpuset on
        # container is actually set
        # For memory, lxc does not respect it but libvirt requires it in the xml to be defined
        container.update({
            'vcpus': None,
            'cores': None,
            'threads': None,
            'memory': None,
        })

        return ContainerDomain(ContainerDomainConfiguration(**container))


async def __event_system_ready(middleware, event_type, args):
    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service, however, the containers still need to be
    # initialized (which is what the above callers are doing)
    if await middleware.call('failover.licensed'):
        return

    middleware.create_task(middleware.call('container.start_on_boot'))


async def __event_system_shutdown(middleware, event_type, args):
    middleware.create_task(middleware.call('container.handle_shutdown'))


async def setup(middleware):
    middleware.event_subscribe('system.ready', __event_system_ready)
    middleware.event_subscribe('system.shutdown', __event_system_shutdown)
