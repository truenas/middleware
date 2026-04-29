from truenas_pylibvirt.nsexec import ALL_CAPABILITIES, build_argv_for_shell

from middlewared.service import CallError, private, Service


# Re-exported under the legacy name so existing consumers
# (`from .nsenter import CAPABILITIES`) keep working.
CAPABILITIES = ALL_CAPABILITIES


class ContainerService(Service):
    @private
    def nsenter(self, container):
        """
        Produces a command that can be used to execute commands inside the container.
        :param container: container as returned by `container.query`
        """
        if container["status"]["pid"] is None:
            raise CallError("Container is not running")

        return build_argv_for_shell(
            uuid=container["uuid"],
            uri=self.middleware.libvirt_domains_manager.containers_connection.uri,
            capabilities_policy=container["capabilities_policy"],
            capabilities_state=container["capabilities_state"],
            has_idmap=bool(container["idmap"]),
            shell_argv=["/bin/sh", "-c"],
        )
