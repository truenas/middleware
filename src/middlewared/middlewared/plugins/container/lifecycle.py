from truenas_pylibvirt import (
    ContainerCapabilitiesPolicy, ContainerDomain, ContainerDomainConfiguration, ContainerIdmapConfiguration,
    ContainerIdmapConfigurationItem, NICDevice, NICDeviceType, Time,
)

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerStartArgs, ContainerStartResult,
    ContainerStopArgs, ContainerStopResult,
)
from middlewared.service import private, Service


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
        container["root"] = f"/mnt/{container.pop('dataset')}"
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
            container["idmap"] = ContainerIdmapConfiguration(
                uid=ContainerIdmapConfigurationItem(**container["idmap"]["uid"]),
                gid=ContainerIdmapConfigurationItem(**container["idmap"]["gid"]),
            )

        if container["capabilities_policy"]:
            container["capabilities_policy"] = ContainerCapabilitiesPolicy[container["capabilities_policy"]]

        return ContainerDomain(ContainerDomainConfiguration(**container))
