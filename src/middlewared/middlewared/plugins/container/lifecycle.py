from truenas_pylibvirt import ContainerDomain, ContainerDomainConfiguration, Time

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerStartArgs, ContainerStartResult,
    ContainerStopArgs, ContainerStopResult,
)
from middlewared.service import private, Service


class ContainerService(Service):
    @api_method(ContainerStartArgs, ContainerStartResult, roles=["CONTAINER_WRITE"])
    def start(self, id_):
        container = self.middleware.call_sync("container.get_instance", id_)
        self.middleware.libvirt_domains_manager.containers.start(self.pylibvirt_container(container))

    @api_method(ContainerStopArgs, ContainerStopResult, roles=["CONTAINER_WRITE"])
    def stop(self, id_, options):
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
        container["devices"] = []

        return ContainerDomain(ContainerDomainConfiguration(**container))
