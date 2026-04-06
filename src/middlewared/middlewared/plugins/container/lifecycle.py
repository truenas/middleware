import errno
import typing

from truenas_pylibvirt import (
    ContainerCapabilitiesPolicy, ContainerDomain, ContainerDomainConfiguration, ContainerIdmapConfiguration,
    ContainerIdmapConfigurationItem, NICDevice, NICDeviceType, Time,
)

from middlewared.api.current import ContainerStopOptions, QueryOptions, ZFSResourceQuery
from middlewared.plugins.account_.constants import CONTAINER_ROOT_UID
from middlewared.service import CallError, ServiceContext

from .bridge import container_bridge_name, configure_container_bridge
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
        item = None
        match container['idmap']['type']:
            case 'DEFAULT':
                item = ContainerIdmapConfigurationItem(
                    target=CONTAINER_ROOT_UID,
                    count=IDMAP_COUNT,
                )
            case 'ISOLATED':
                item = ContainerIdmapConfigurationItem(
                    target=CONTAINER_ROOT_UID + container['idmap']['slice'] * IDMAP_COUNT,
                    count=IDMAP_COUNT,
                )
            case _:
                raise CallError(f"Unsupported idmap type {container['idmap']['type']!r}")

        container['idmap'] = ContainerIdmapConfiguration(uid=item, gid=item)

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
