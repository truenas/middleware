import errno
import typing

from truenas_pylibvirt import (
    ContainerCapabilitiesPolicy,
    ContainerDomain,
    ContainerDomainConfiguration,
    ContainerIdmapConfiguration,
    ContainerIdmapConfigurationItem,
    NICDevice,
    NICDeviceType,
    Time,
)

from middlewared.api.current import ContainerStopOptions, QueryOptions, ZFSResourceQuery
from middlewared.plugins.account_.constants import CONTAINER_ROOT_UID
from middlewared.service import CallError, ServiceContext

from .bridge import configure_container_bridge, container_bridge_name
from .utils import container_instance_dataset_mountpoint, update_etc_hosts, write_etc_hostname

IDMAP_COUNT = 65536


def start_on_boot(context: ServiceContext) -> None:
    for container in context.call_sync2(
        context.s.container.query, [('autostart', '=', True)], QueryOptions(force_sql_filters=True)
    ):
        try:
            start(context, container.id)
        except Exception as e:
            context.logger.error(f'Failed to start {container.name!r} container: {e}')


def handle_shutdown(context: ServiceContext) -> None:
    for container in context.call_sync2(context.s.container.query, [('status.state', '=', 'RUNNING')]):
        stop(context, container.id, ContainerStopOptions(force_after_timeout=True))


def start(context: ServiceContext, id_: int) -> None:
    container = context.run_coroutine(context.call2(context.s.container.get_instance, id_))
    configure_container_bridge(context)

    pylibvirt_obj = pylibvirt_container(context, container.model_dump(by_alias=True), True)

    # Configure hostname files before start so init reads correct values
    try:
        write_etc_hostname(pylibvirt_obj.configuration.root, container.name)
        update_etc_hosts(pylibvirt_obj.configuration.root, container.name)
    except Exception:
        context.logger.warning('Failed to configure hostname for container %r', container.name, exc_info=True)

    context.middleware.libvirt_domains_manager.containers.start(pylibvirt_obj)


def stop(context: ServiceContext, id_: int, options: ContainerStopOptions) -> None:
    container = context.run_coroutine(context.call2(context.s.container.get_instance, id_))
    pylibvirt_container_obj = pylibvirt_container(context, container.model_dump(by_alias=True))
    if options.force:
        context.middleware.libvirt_domains_manager.containers.destroy(pylibvirt_container_obj)
        return

    context.middleware.libvirt_domains_manager.containers.shutdown(pylibvirt_container_obj)
    if options.force_after_timeout and context.run_coroutine(
        context.call2(context.s.container.get_instance, id_)
    ).status.state == 'RUNNING':
        context.middleware.libvirt_domains_manager.containers.destroy(pylibvirt_container_obj)


def pylibvirt_container(
    context: ServiceContext, container: dict[str, typing.Any], check_ds: bool = False
) -> ContainerDomain:
    container = container.copy()
    container.pop('id', None)
    container.pop('status', None)
    container.pop('autostart', None)
    container.pop('default_network', None)

    dataset = container.pop('dataset')
    pool = dataset.split('/')[0]
    container['root'] = f"/mnt/{container_instance_dataset_mountpoint(pool, container['name'])}"
    if check_ds:
        datasets = context.call_sync2(
            context.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[dataset], properties=None),
        )
        if not datasets:
            raise CallError(f'Dataset {dataset!r} not found', errno.ENOTDIR)

    container['time'] = Time(container['time'])
    device_factory = context.middleware.services.container.device.device_factory
    devices = []
    has_nic_device = False
    for device in container.get('devices', []):
        if device['attributes']['dtype'] == 'NIC':
            has_nic_device = True

        devices.append(device_factory.get_device(device))

    if not has_nic_device:
        # Add one if one isn't added already
        # TODO: See if this should be desired behaviour
        devices.append(
            NICDevice(
                type_=NICDeviceType.BRIDGE,
                source=container_bridge_name(context),
                model=None,
                mac=None,
                trust_guest_rx_filters=False,
            )
        )

    container['devices'] = devices

    if container['idmap']:
        match container['idmap']['type']:
            case 'DEFAULT':
                uid_items, gid_items = _build_default_idmap_items(context)
            case 'ISOLATED':
                base_target = CONTAINER_ROOT_UID + container['idmap']['slice'] * IDMAP_COUNT
                single = ContainerIdmapConfigurationItem(start=0, target=base_target, count=IDMAP_COUNT)
                uid_items, gid_items = [single], [single]
            case _:
                raise CallError(f"Unsupported idmap type {container['idmap']['type']!r}")

        try:
            container['idmap'] = ContainerIdmapConfiguration(uid=uid_items, gid=gid_items)
        except ValueError as e:
            raise CallError(f'Invalid idmap configuration: {e}')

    if container['capabilities_policy']:
        container['capabilities_policy'] = ContainerCapabilitiesPolicy[container['capabilities_policy']]

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


def _build_default_idmap_items(
    context: ServiceContext,
) -> tuple[list[ContainerIdmapConfigurationItem], list[ContainerIdmapConfigurationItem]]:
    idmap_filters = [
        ['local', '=', True],
        ['userns_idmap', 'nin', [0, None]],
        ['roles', '=', []],
    ]
    users = context.middleware.call_sync('user.query', idmap_filters)
    groups = context.middleware.call_sync('group.query', idmap_filters)

    uid_passthroughs = [_resolve_target(u['uid'], u['userns_idmap']) for u in users]
    gid_passthroughs = [_resolve_target(g['gid'], g['userns_idmap']) for g in groups]

    return _build_idmap_items(uid_passthroughs), _build_idmap_items(gid_passthroughs)


def _resolve_target(account_id: int, userns_idmap: typing.Any) -> tuple[int, int]:
    """Resolve an account's userns_idmap setting to a (container_id, host_id) pair.

    'DIRECT' means the host UID/GID is exposed inside the container with the same
    numeric value (container_id == host_id). Any other value is the explicit
    container-side ID that should map to the host's UID/GID.
    """
    container_id = account_id if userns_idmap == 'DIRECT' else userns_idmap
    return container_id, account_id


def _build_idmap_items(
    passthroughs: list[tuple[int, int]],
) -> list[ContainerIdmapConfigurationItem]:
    """Build a complete idmap table around per-account passthroughs.

    For each passthrough whose container-side ID falls in [0, IDMAP_COUNT), emit
    a single-ID entry mapping that slot to the account's host ID. Slots not
    covered by any passthrough are filled with mappings into the shifted
    CONTAINER_ROOT_UID range so the container has a complete unprivileged
    UID/GID space. Passthroughs whose container-side ID falls outside
    [0, IDMAP_COUNT) are appended verbatim as individual one-ID entries.

    Raises CallError when two passthroughs resolve to the same in-range
    container-side ID. Account-level validation should catch this before
    persistence; the check here is a safety net.
    """
    in_range: list[tuple[int, int]] = []
    out_of_range: list[tuple[int, int]] = []
    for c, h in passthroughs:
        if 0 <= c < IDMAP_COUNT:
            in_range.append((c, h))
        else:
            out_of_range.append((c, h))
    in_range.sort()

    items: list[ContainerIdmapConfigurationItem] = []
    cursor = 0
    for container_id, host_id in in_range:
        if container_id < cursor:
            raise CallError(
                f'Duplicate container-side id {container_id} in account idmap configuration'
            )
        if container_id > cursor:
            items.append(ContainerIdmapConfigurationItem(
                start=cursor,
                target=CONTAINER_ROOT_UID + cursor,
                count=container_id - cursor,
            ))
        items.append(ContainerIdmapConfigurationItem(
            start=container_id, target=host_id, count=1,
        ))
        cursor = container_id + 1

    if cursor < IDMAP_COUNT:
        items.append(ContainerIdmapConfigurationItem(
            start=cursor,
            target=CONTAINER_ROOT_UID + cursor,
            count=IDMAP_COUNT - cursor,
        ))

    for container_id, host_id in out_of_range:
        items.append(ContainerIdmapConfigurationItem(
            start=container_id, target=host_id, count=1,
        ))

    return items
