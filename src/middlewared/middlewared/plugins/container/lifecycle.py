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
from middlewared.service import CallError, private, Service


class ContainerService(Service):
    @api_method(ContainerStartArgs, ContainerStartResult, roles=["CONTAINER_WRITE"])
    def start(self, id_):
        """Start container."""
        container = self.middleware.call_sync("container.get_instance", id_)

        self.middleware.call_sync("container.configure_bridge")

        self.middleware.libvirt_domains_manager.containers.start(self.pylibvirt_container(container))

    @api_method(ContainerStopArgs, ContainerStopResult, roles=["CONTAINER_WRITE"])
    def stop(self, id_, options):
        """Start container."""
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
    def pylibvirt_container(self, container):
        container = container.copy()
        container.pop("id", None)
        container.pop("status", None)

        dataset = container.pop("dataset")
        datasets = self.middleware.call_sync(
            'zfs.resource.query_impl', {'paths': [dataset], 'properties': ['mountpoint']}
        )
        if not datasets:
            raise CallError(f"Dataset {dataset!r} not found", errno.ENOTDIR)

        container["root"] = datasets[0]["properties"]["mountpoint"]["value"]
        container["time"] = Time(container["time"])
        container["devices"] = [
            NICDevice(
                type_=NICDeviceType.BRIDGE,
                source=self.middleware.call_sync("container.bridge_name"),
                model=None,
                mac=None,
                trust_guest_rx_filters=False,
            )
        ]

        if container["idmap"]:
            if container["idmap"] == "DEFAULT":
                item = ContainerIdmapConfigurationItem(
                    target=CONTAINER_ROOT_UID,
                    count=65536,
                )
            else:
                item = ContainerIdmapConfigurationItem(**container["idmap"])

            container["idmap"] = ContainerIdmapConfiguration(uid=item, gid=item)

        if container["capabilities_policy"]:
            container["capabilities_policy"] = ContainerCapabilitiesPolicy[container["capabilities_policy"]]

        return ContainerDomain(ContainerDomainConfiguration(**container))
