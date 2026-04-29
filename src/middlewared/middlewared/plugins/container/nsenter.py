from truenas_pylibvirt.nsexec import build_argv_for_shell

from middlewared.service import CallError, ServiceContext


async def nsenter(context: ServiceContext, container_id: int) -> list[str]:
    container = await context.call2(context.s.container.get_instance, container_id)
    if container.status.pid is None:
        raise CallError("Container is not running")

    return build_argv_for_shell(
        uuid=container.uuid,
        uri=context.middleware.libvirt_domains_manager.containers_connection.uri,
        capabilities_policy=container.capabilities_policy,
        capabilities_state=container.capabilities_state,
        has_idmap=bool(container.idmap),
        shell_argv=["/bin/sh", "-c"],
    )
