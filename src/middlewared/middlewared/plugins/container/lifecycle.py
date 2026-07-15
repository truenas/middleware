import asyncio
import errno
import os

import truenas_os
from truenas_pylibvirt import (
    ContainerCapabilitiesPolicy, ContainerDomain, ContainerDomainConfiguration, ContainerIdmapConfiguration,
    ContainerIdmapConfigurationItem, NICDevice, NICDeviceType, Time,
)

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerStartArgs, ContainerStartResult,
    ContainerStopArgs, ContainerStopResult,
    ZFSResourceQuery
)
from middlewared.plugins.account_.constants import CONTAINER_ROOT_UID, IDMAP_COUNT
from middlewared.service import CallError, job, private, Service
from middlewared.utils.filesystem.perms import enforce_dir_perms

from .bridge import container_bridge_name, configure_container_bridge
from .dataset import CONTAINER_DS_PARENT_DIR
from .utils import container_instance_dataset_mountpoint, update_etc_hosts, write_etc_hostname

IDMAPPED_ROOT_DIR = '/run/truenas_containers/root'

# The full enumeration of host UIDs any container's container-uid-0 ever
# maps to: CONTAINER_ROOT_UID + slice*IDMAP_COUNT for slice in range(1000).
# - slice 0 is the DEFAULT-idmap row (stored internally; not user-settable).
# - slice [1, 999] is the ISOLATED range per api/v27_0_0/container.py
#   (PositiveInt with lt=1000).
# - ContainerXID is `ge=1` in api/base/types/user.py, so no local account
#   can ever claim container-uid 0; container 0 therefore always maps to
#   CONTAINER_ROOT_UID + slice*IDMAP_COUNT for some slice in this range.
# Static set -> no per-container ACL bookkeeping at all.
_IDMAPPED_ROOT_ALLOWED_UIDS = frozenset(
    CONTAINER_ROOT_UID + n * IDMAP_COUNT for n in range(1000)
)


def apply_idmapped_root_acl() -> None:
    """Pin IDMAPPED_ROOT_DIR to root:root with a POSIX1E ACL granting `--x`
    (search only) to every possible container-uid-0 host UID. Idempotent;
    called from etc-render at boot and from container.start as drift repair.

    fsetacl writes UGO/MASK through to the legacy mode bits, so a single
    fsetacl is sole source of truth for both the ACL and the mode (visible
    as 0o710 because MASK ends up in the group triad).
    """
    os.makedirs(IDMAPPED_ROOT_DIR, mode=0o700, exist_ok=True)
    fd = truenas_os.openat2(
        IDMAPPED_ROOT_DIR,
        flags=os.O_DIRECTORY,
        resolve=truenas_os.RESOLVE_NO_SYMLINKS,
    )
    try:
        st = os.fstat(fd)
        if st.st_uid != 0 or st.st_gid != 0:
            os.fchown(fd, 0, 0)
        truenas_os.fsetacl(fd, _build_idmapped_root_acl())
    finally:
        os.close(fd)


def _build_idmapped_root_acl() -> 'truenas_os.POSIXACL':
    P, T = truenas_os.POSIXPerm, truenas_os.POSIXTag
    rwx = P.READ | P.WRITE | P.EXECUTE
    nothing = P(0)
    aces = [
        truenas_os.POSIXAce(T.USER_OBJ, rwx),
        truenas_os.POSIXAce(T.GROUP_OBJ, nothing),
    ]
    for uid in sorted(_IDMAPPED_ROOT_ALLOWED_UIDS):
        aces.append(truenas_os.POSIXAce(T.USER, P.EXECUTE, id=uid))
    aces.append(truenas_os.POSIXAce(T.MASK, P.EXECUTE))
    aces.append(truenas_os.POSIXAce(T.OTHER, nothing))
    return truenas_os.POSIXACL.from_aces(aces)


async def _stop_one_container(middleware, container):
    try:
        job = await middleware.call(
            'container.stop', container['id'], {'force_after_timeout': True},
        )
        await job.wait(raise_error=True)
    except Exception:
        middleware.logger.error('Failed to stop %r container', container['name'], exc_info=True)


class ContainerService(Service):

    @private
    async def start_on_boot(self):
        # Reap orphaned runtime state under /run/truenas_containers/ before any
        # autostart so a fresh start can't collide with a leaked staged path
        # from a previous unclean shutdown (libvirtd or middlewared crash).
        try:
            await self.middleware.run_in_thread(
                self.middleware.libvirt_domains_manager.reconcile_runtime_state
            )
        except Exception:
            self.middleware.logger.error(
                'Failed to reconcile container runtime state', exc_info=True
            )

        for container in await self.middleware.call(
            'container.query', [('autostart', '=', True)], {'force_sql_filters': True}
        ):
            try:
                await self.middleware.call('container.start', container['id'])
            except Exception as e:
                self.middleware.logger.error(f'Failed to start {container["name"]!r} container: {e}')

    @private
    async def handle_shutdown(self):
        running = await self.middleware.call('container.query', [('status.state', '=', 'RUNNING')])
        await asyncio.gather(*(_stop_one_container(self.middleware, c) for c in running))

    @api_method(ContainerStartArgs, ContainerStartResult, roles=["CONTAINER_WRITE"])
    def start(self, id_):
        """Start container."""
        enforce_dir_perms(CONTAINER_DS_PARENT_DIR)
        apply_idmapped_root_acl()

        container = self.middleware.call_sync("container.get_instance", id_)
        configure_container_bridge(self)

        pylibvirt_obj = self.pylibvirt_container(container, True)

        # Configure hostname files before start so init reads correct values
        try:
            write_etc_hostname(pylibvirt_obj.configuration.root, container['name'])
            update_etc_hosts(pylibvirt_obj.configuration.root, container['name'])
        except Exception:
            self.logger.warning('Failed to configure hostname for container %r', container['name'], exc_info=True)

        self.middleware.libvirt_domains_manager.containers.start(pylibvirt_obj)

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
        container.pop('default_network', None)

        dataset = container.pop("dataset")
        pool = dataset.split("/")[0]
        container["root"] = f"/mnt/{container_instance_dataset_mountpoint(pool, container['name'])}"
        if check_ds:
            datasets = self.call_sync2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(paths=[dataset], properties=None),
            )
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
                    source=container_bridge_name(self),
                    model=None,
                    mac=None,
                    trust_guest_rx_filters=False,
                )
            )

        container["devices"] = devices

        if container["idmap"]:
            match container["idmap"]["type"]:
                case "DEFAULT":
                    uid_items, gid_items = self._build_default_idmap_items()
                case "ISOLATED":
                    base_target = CONTAINER_ROOT_UID + container["idmap"]["slice"] * IDMAP_COUNT
                    single = ContainerIdmapConfigurationItem(start=0, target=base_target, count=IDMAP_COUNT)
                    uid_items, gid_items = [single], [single]
                case _:
                    raise CallError(f"Unsupported idmap type {container['idmap']['type']!r}")

            try:
                container["idmap"] = ContainerIdmapConfiguration(uid=uid_items, gid=gid_items)
            except ValueError as e:
                raise CallError(f"Invalid idmap configuration: {e}")

        if container["capabilities_policy"]:
            container["capabilities_policy"] = ContainerCapabilitiesPolicy[container["capabilities_policy"]]

        # For a privileged (no user namespace) container, "allow all" keeps every
        # capability in the bounding set but libvirt only widens the cgroup device
        # ACL — which permits creating device nodes such as the overlayfs whiteouts
        # produced during container-image extraction — when an explicit
        # <mknod state='on'/> is emitted. Inject it so "allow all" also allows
        # device-node creation, unless the user set mknod explicitly. This is
        # skipped for user-namespaced containers, where the device ACL is not the
        # operative gate (the user namespace is) and the element would be a no-op.
        if (
            container["capabilities_policy"] == ContainerCapabilitiesPolicy.ALLOW
            and container["idmap"] is None
            and "mknod" not in container["capabilities_state"]
        ):
            container["capabilities_state"] = {**container["capabilities_state"], "mknod": True}

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

    @private
    def _build_default_idmap_items(self):
        idmap_filters = [
            ['local', '=', True],
            ['userns_idmap', 'nin', [0, None]],
            ['roles', '=', []],
        ]
        users = self.middleware.call_sync('user.query', idmap_filters)
        groups = self.middleware.call_sync('group.query', idmap_filters)

        uid_passthroughs = [_resolve_target(u['uid'], u['userns_idmap']) for u in users]
        gid_passthroughs = [_resolve_target(g['gid'], g['userns_idmap']) for g in groups]

        return _build_idmap_items(uid_passthroughs), _build_idmap_items(gid_passthroughs)


def _resolve_target(account_id, userns_idmap):
    """Resolve an account's userns_idmap setting to a (container_id, host_id) pair.

    'DIRECT' means the host UID/GID is exposed inside the container with the same
    numeric value (container_id == host_id). Any other value is the explicit
    container-side ID that should map to the host's UID/GID.
    """
    container_id = account_id if userns_idmap == 'DIRECT' else userns_idmap
    return container_id, account_id


def _build_idmap_items(passthroughs):
    """Build a complete idmap table around per-account passthroughs.

    For each passthrough whose container-side ID falls in [0, IDMAP_COUNT), emit
    a single-ID entry mapping that slot to the account's host ID. Slots not
    covered by any passthrough are filled with mappings into the shifted
    CONTAINER_ROOT_UID range so the container has a complete unprivileged
    UID/GID space. Passthroughs whose container-side ID falls outside
    [0, IDMAP_COUNT) are appended verbatim as individual one-ID entries.

    Account-level validation rejects duplicate container-side IDs before
    persistence; the deduplication check here is a safety net for stale or
    corrupt account state. Host-side overlaps are caught downstream by
    ContainerIdmapConfiguration validation.
    """
    seen = set()
    for container_id, _ in passthroughs:
        if container_id in seen:
            raise CallError(
                f'Duplicate container-side id {container_id} in account idmap configuration'
            )
        seen.add(container_id)

    in_range = []
    out_of_range = []
    for c, h in passthroughs:
        if 0 <= c < IDMAP_COUNT:
            in_range.append((c, h))
        else:
            out_of_range.append((c, h))
    in_range.sort()

    items = []
    cursor = 0
    for container_id, host_id in in_range:
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


async def __migrate_and_start(middleware):
    await middleware.call('container.maybe_migrate_legacy')
    await middleware.call('container.start_on_boot')


async def __event_system_ready(middleware, event_type, args):
    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service, however, the containers still need to be
    # initialized (which is what the above callers are doing)
    if await middleware.call('failover.licensed'):
        return

    middleware.create_task(__migrate_and_start(middleware))


async def __event_system_shutdown(middleware, event_type, args):
    middleware.create_task(middleware.call('container.handle_shutdown'))


async def setup(middleware):
    middleware.event_subscribe('system.ready', __event_system_ready)
    middleware.event_subscribe('system.shutdown', __event_system_shutdown)
