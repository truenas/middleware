"""System dataset.

The system dataset is a hierarchy of ZFS datasets rooted at <pool>/.system
that holds non-pool-resident state (samba4 cache, NFS state, VM nvram,
netdata metrics, etc.). It can live on the boot pool or any imported data
pool, and may be migrated between pools without service downtime beyond a
brief quiesce of the few daemons that hold open handles into it.

Mount mechanics and replication live in `system_dataset.mount`:

- `mount_hierarchy` mounts the parent .system dataset and nests each child
  inside it via fsopen/fsconfig/fsmount + move_mount (the new mount API,
  no fork/exec).
- `swap_under` does the atomic mount swap via MOVE_MOUNT_BENEATH so the
  destination path is never bare during the cutover.
- `replicate` does the data transfer: one atomic lzc_snapshot covers the
  whole source hierarchy, then per-dataset lzc.send | lzc.receive piped
  between threads.

This module orchestrates: configuration validation, pool selection, the
release/restart of consumer daemons during the cutover, post-mount setup
(ACL check, cores → coredump bind), and the failover-related flows.
"""
from contextlib import contextmanager, suppress
import errno
import os
from pathlib import Path
import shutil
import tempfile
import threading
import uuid

import truenas_os
from truenas_os_pyutils.mount import iter_mountinfo, statmount, umount

from middlewared.api import api_method
from middlewared.api.current import (
    SystemDatasetEntry,
    SystemDatasetPoolChoicesArgs,
    SystemDatasetPoolChoicesResult,
    SystemDatasetUpdateArgs,
    SystemDatasetUpdateResult,
    ZFSResourceQuery,
)
from middlewared.plugins.pool_.utils import CreateImplArgs, UpdateImplArgs
from middlewared.plugins.system_dataset.hierarchy import get_system_dataset_spec
from middlewared.plugins.system_dataset.mount import (
    mount_hierarchy,
    replicate,
    swap_under,
)
from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH
from middlewared.plugins.zfs.exceptions import ZFSPathNotFoundException
from middlewared.plugins.zfs.utils import get_encryption_info
from middlewared.service import CallError, ConfigService, ValidationError, ValidationErrors, job, private
import middlewared.sqlalchemy as sa
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.size import format_size
from middlewared.utils.tdb import close_sysdataset_tdb_handles
from middlewared.utils.zfs import query_imported_fast_impl

# systemd writes coredumps here; we bind <SYSDATASET>/cores onto it so
# coredumps land on persistent storage instead of the boot pool.
_COREDUMP_PATH = '/var/lib/systemd/coredump'


class SystemDatasetModel(sa.Model):
    __tablename__ = 'system_systemdataset'

    id = sa.Column(sa.Integer(), primary_key=True)
    sys_pool = sa.Column(sa.String(1024))
    sys_uuid = sa.Column(sa.String(32))
    sys_uuid_b = sa.Column(sa.String(32), nullable=True)


class SystemDatasetService(ConfigService):

    class Config:
        datastore = 'system.systemdataset'
        datastore_extend = 'systemdataset.config_extend'
        datastore_prefix = 'sys_'
        cli_namespace = 'system.system_dataset'
        role_prefix = 'DATASET'
        entry = SystemDatasetEntry

    force_pool = None
    sysdataset_release_lock = threading.Lock()

    @private
    def sysdataset_path(self, expected_datasetname=None):
        """
        Returns SYSDATASET_PATH if the expected dataset is mounted there,
        otherwise None. Called frequently — single statmount probe.
        """
        if expected_datasetname is None:
            db_pool = self.middleware.call_sync(
                'datastore.config', 'system.systemdataset',
            )['sys_pool']
            pool = self.force_pool or db_pool or self.middleware.call_sync('boot.pool_name')
            ds_name = f'{pool}/.system'
        else:
            ds_name = expected_datasetname

        try:
            mntinfo = statmount(path=SYSDATASET_PATH, as_dict=False)
        except FileNotFoundError:
            self.logger.warning('%s: mountpoint not found', SYSDATASET_PATH)
            return None

        if mntinfo.sb_source != ds_name:
            self.logger.warning(
                'Unexpected dataset mounted at %s, %r present, but %r expected.',
                SYSDATASET_PATH, mntinfo.sb_source, ds_name,
            )
            return None

        return SYSDATASET_PATH

    @private
    async def config_extend(self, config):
        # Empty pool is treated as boot pool.
        config['pool_set'] = bool(config['pool'])
        config['pool'] = self.force_pool or config['pool'] or await self.middleware.call('boot.pool_name')
        config['basename'] = f'{config["pool"]}/.system'

        # `uuid` always reflects the local node (B uses uuid_b).
        uuid_key = 'uuid'
        if await self.middleware.call('failover.node') == 'B':
            uuid_key = 'uuid_b'
            config['uuid'] = config['uuid_b']
        del config['uuid_b']

        if not config['uuid']:
            config['uuid'] = uuid.uuid4().hex
            await self.middleware.call(
                'datastore.update', 'system.systemdataset', config['id'],
                {uuid_key: config['uuid']}, {'prefix': 'sys_'},
            )

        config['path'] = await self.middleware.run_in_thread(self.sysdataset_path, config['basename'])
        return config

    @private
    async def ensure_standby_uuid(self):
        remote_uuid_key = 'uuid_b'
        if await self.middleware.call('failover.node') == 'B':
            remote_uuid_key = 'uuid'

        local_config = await self.middleware.call(
            'datastore.config', 'system.systemdataset', {'prefix': 'sys_'},
        )
        if local_config[remote_uuid_key]:
            self.logger.debug('We already know the standby controller system dataset UUID')
            return

        remote_config = await self.middleware.call(
            'failover.call_remote', 'datastore.config',
            ['system.systemdataset', {'prefix': 'sys_'}],
        )
        if not remote_config[remote_uuid_key]:
            self.logger.warning('Standby controller does not yet have the system dataset UUID')
            return

        self.logger.info(f'Setting {remote_uuid_key}={remote_config[remote_uuid_key]!r}')
        await self.middleware.call(
            'datastore.update', 'system.systemdataset', local_config['id'],
            {remote_uuid_key: remote_config[remote_uuid_key]}, {'prefix': 'sys_'},
        )

    @private
    async def is_boot_pool(self):
        pool = (await self.config())['pool']
        if not pool:
            raise CallError('System dataset pool is not set. This may prevent '
                            'system services from functioning properly.')
        return pool in BOOT_POOL_NAME_VALID

    @api_method(SystemDatasetPoolChoicesArgs, SystemDatasetPoolChoicesResult, roles=['POOL_READ'])
    async def pool_choices(self, include_current_pool):
        """Retrieve pool choices which can be used for configuring system dataset."""
        boot_pool = await self.middleware.call('boot.pool_name')
        current_pool = (await self.config())['pool']
        valid_pools = await self.middleware.call('systemdataset.query_pools_for_system_dataset')

        pools = [boot_pool]
        if include_current_pool:
            pools.append(current_pool)
        pools.extend(valid_pools)
        return {p: p for p in sorted(set(pools))}

    @api_method(SystemDatasetUpdateArgs, SystemDatasetUpdateResult)
    @job(lock='sysdataset_update')
    async def do_update(self, job, data):
        """Update System Dataset Service Configuration.

        Records the user's pool selection in the datastore and triggers
        setup. setup_impl detects pool changes (configured-vs-mounted) and
        runs the migration; do_update itself does not.
        """
        data.setdefault('pool_exclude', None)
        config = await self.config()
        new_pool = await self._validate_and_select_pool(data, config)

        await self.middleware.call(
            'datastore.update', 'system.systemdataset', config['id'],
            {'pool': new_pool or ''}, {'prefix': 'sys_'},
        )
        await self.middleware.call('systemdataset.setup', data['pool_exclude'])
        return await self.config()

    async def _validate_and_select_pool(self, data, config):
        """Validate the requested pool and return the pool name to record."""
        verrors = ValidationErrors()
        new_pool = data.get('pool', config['pool'])

        if new_pool and new_pool != config['pool']:
            if error := await self.destination_pool_error(new_pool):
                verrors.add('sysdataset_update.pool', error)

        if new_pool and new_pool not in await self.pool_choices(False):
            verrors.add(
                'sysdataset_update.pool',
                'The system dataset cannot be placed on this pool.',
            )

        verrors.check()
        return new_pool

    @private
    async def destination_pool_error(self, new_pool):
        config = await self.config()
        existing_dataset = new_dataset = None
        for i in await self.call2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[config['basename'], new_pool], properties=['used', 'available']),
        ):
            if i['name'] == config['basename']:
                existing_dataset = i
            elif i['name'] == new_pool:
                new_dataset = i

        if not existing_dataset:
            return
        if not new_dataset:
            return f'Dataset {new_pool} does not exist'

        used = existing_dataset['properties']['used']['value']
        available = new_dataset['properties']['available']['value']
        # 1.1× margin: same files don't take exactly the same amount of
        # space on a different pool.
        used = int(used * 1.1)
        if available < used:
            return (
                f'Insufficient disk space available on {new_pool} ({format_size(available)}). '
                f'Need {format_size(used)}'
            )

    @private
    def setup(self, exclude_pool: str | None = None):
        self.middleware.call_hook_sync('sysdataset.setup', data={'in_progress': True})
        try:
            return self.setup_impl(exclude_pool)
        finally:
            self.middleware.call_hook_sync('sysdataset.setup', data={'in_progress': False})

    @private
    def setup_impl(self, exclude_pool):
        """Bring SYSDATASET_PATH into a known-good state.

        - Pick the target pool (configured pool if available, otherwise a
          fallback) via select_system_dataset_pool.
        - If we picked something other than the configured pool and it's
          NOT a temporary fallback, persist the change to the datastore
          directly. (We can't go through systemdataset.update from here:
          do_update holds the sysdataset_update job lock and re-entering
          would deadlock.)
        - If something is mounted at SYSDATASET_PATH from a different
          pool, run migrate to move the data over.
        - Otherwise ensure spec datasets exist with right properties and
          mount whatever isn't mounted yet.
        - Run post-mount setup: ACL check + cores→coredump bind.
        """
        self.force_pool = None
        config = self.middleware.call_sync('systemdataset.config')

        # Read the user's preferred pool from the database (config['pool']
        # has already been mangled to fall back to boot pool if blank).
        preferred_pool = self.middleware.call_sync(
            'datastore.config', 'system_systemdataset',
        )['sys_pool']
        target_pool, is_fallback = self.select_system_dataset_pool(
            preferred_pool=preferred_pool, exclude_pool=exclude_pool,
        )

        if target_pool != config['pool'] and not is_fallback:
            self.logger.debug(
                'Updating system dataset pool from %r to %r', config['pool'], target_pool,
            )
            self.middleware.call_sync(
                'datastore.update', 'system.systemdataset', config['id'],
                {'pool': target_pool}, {'prefix': 'sys_'},
            )
            config = self.middleware.call_sync('systemdataset.config')
        elif is_fallback:
            self.force_pool = target_pool
            config = self.middleware.call_sync('systemdataset.config')

        if not os.path.isdir(SYSDATASET_PATH) and os.path.exists(SYSDATASET_PATH):
            os.unlink(SYSDATASET_PATH)
        os.makedirs(SYSDATASET_PATH, mode=0o755, exist_ok=True)

        try:
            sysds_mntinfo = statmount(path=SYSDATASET_PATH)
            if sysds_mntinfo['mount_source'] and sysds_mntinfo['mount_source'].endswith('.system'):
                mounted_pool = sysds_mntinfo['mount_source'].split('/')[0]
            else:
                mounted_pool = None
        except FileNotFoundError:
            mounted_pool = None

        # Wrong pool's dataset is mounted — migrate.
        if mounted_pool and mounted_pool != target_pool:
            self.logger.debug(
                'Migrating system dataset from %r to %r', mounted_pool, target_pool,
            )
            self.migrate(mounted_pool, target_pool)
            return self.middleware.call_sync('systemdataset.config')

        # Same pool (or nothing mounted) — ensure datasets and mount.
        datasets = self.middleware.call_sync(
            'systemdataset.setup_datasets', target_pool, config['uuid'],
        )
        if not mounted_pool:
            self.mount_system_dataset(datasets)

        self._post_mount_setup()
        return self.middleware.call_sync('systemdataset.config')

    @private
    def query_pools_for_system_dataset(self, exclude_pool=None):
        """Pools eligible to host the system dataset.

        Pools with passphrase-locked roots are eligible because ZFS
        encryption is per-dataset and the system dataset uses a legacy
        mount; key format is only exposed via libzfs, so reading mountinfo
        here is insufficient.
        """
        rv = []
        for i in query_imported_fast_impl().values():
            if (exclude_pool and exclude_pool == i['name']) or i['name'] in BOOT_POOL_NAME_VALID:
                continue

            ds = self.call_sync2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(paths=[i['name']], properties=['encryption']),
            )
            if not ds:
                continue

            enc = get_encryption_info(ds[0]['properties'])
            if not enc.encrypted or not enc.locked or enc.encryption_type == 'passphrase':
                rv.append(i['name'])
        return rv

    @private
    def select_system_dataset_pool(self, preferred_pool=None, exclude_pool=None):
        """Pick which pool should host the system dataset.

        Returns: (pool_name, is_temporary_fallback)

        Priority:
          1. preferred_pool, if it's importable and not key-locked
          2. first available non-boot data pool
          3. boot pool

        is_temporary_fallback=True when the preferred pool is configured
        but currently inaccessible (unimported or root-locked-with-key);
        the caller uses force_pool rather than persisting the fallback.
        """
        boot_pool = self.middleware.call_sync('boot.pool_name')

        if preferred_pool and preferred_pool != exclude_pool:
            if self._pool_is_available(preferred_pool):
                return (preferred_pool, False)
            if preferred_pool != boot_pool:
                self.logger.warning(
                    'Pool %r unavailable, using boot pool temporarily', preferred_pool,
                )
                return (boot_pool, True)

        for pool in self.query_pools_for_system_dataset(exclude_pool):
            return (pool, False)

        return (boot_pool, False)

    def _pool_is_available(self, pool):
        """True if `pool`'s root is mounted and the pool is usable for sysdataset."""
        boot_pool = self.middleware.call_sync('boot.pool_name')
        if pool == boot_pool:
            return True

        for mnt in iter_mountinfo():
            if mnt['mount_source'] == pool:
                return True

        # Not mounted — check whether the root is locked-with-key.
        ds = self.call_sync2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[pool], properties=['encryption']),
        )
        if ds:
            enc = get_encryption_info(ds[0]['properties'])
            if enc.encrypted and enc.locked and enc.encryption_type != 'passphrase':
                return False
        return False

    @private
    async def setup_datasets(self, pool, uuid):
        """Make sure the system datasets for `pool` exist with the right props.

        Returns the spec list (suitable for passing to mount_hierarchy /
        finalize_datasets).
        """
        boot_pool = await self.middleware.call('boot.pool_name')
        # Empty string falls back to boot pool (handles cases where no
        # data pool is selectable).
        pool = pool or boot_pool
        root_dataset_is_passphrase_encrypted = False
        if pool != boot_pool:
            p = await self.call2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(paths=[pool], properties=['encryption']),
            )
            if not p:
                raise ValidationError(
                    'sysdataset_setup_datasets.pool',
                    f'Pool {pool!r} does not exist.',
                    errno.ENOENT,
                )
            enc = get_encryption_info(p[0]['properties'])
            root_dataset_is_passphrase_encrypted = enc.encryption_type == 'passphrase'

        datasets = {i['name']: i for i in get_system_dataset_spec(pool, uuid)}
        datasets_prop = {
            i['name']: i['properties']
            for i in await self.call2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(
                    paths=list(datasets),
                    properties=['encryption', 'quota', 'used', 'mountpoint',
                                'readonly', 'snapdir', 'canmount', 'overlay'],
                ),
            )
        }
        for dataset, config in datasets.items():
            props = config['props']
            # Disable encryption on system-managed children of
            # passphrase-encrypted pools.
            if root_dataset_is_passphrase_encrypted:
                props['encryption'] = 'off'
            # overlayfs is never used on system dataset paths.
            props['overlay'] = 'off'
            is_cores_ds = dataset.endswith('/cores')
            if is_cores_ds:
                # 1G; raw value so the update_props_dict comparison below
                # works (raw values are strings of bytes for sizes).
                props['quota'] = '1073741824'

            if dataset not in datasets_prop:
                await self.middleware.call(
                    'pool.dataset.create_impl',
                    CreateImplArgs(name=dataset, ztype='FILESYSTEM', zprops=props),
                )
            elif is_cores_ds and datasets_prop[dataset]['used']['value'] >= 1024 ** 3:
                try:
                    # bypass=True: <pool>/.system/cores is protected.
                    await self.call2(
                        self.s.zfs.resource.destroy_impl, dataset,
                        recursive=True, bypass=True,
                    )
                    await self.middleware.call(
                        'pool.dataset.create_impl',
                        CreateImplArgs(name=dataset, ztype='FILESYSTEM', zprops=props),
                    )
                except Exception:
                    self.logger.warning("Failed to replace dataset [%s].", dataset, exc_info=True)
            else:
                # Compare via raw values; `value` does some
                # property-specific translation (e.g. raw "on" → True).
                update_props = {
                    k: v for k, v in props.items() if datasets_prop[dataset][k]['raw'] != v
                }
                if update_props:
                    await self.middleware.call(
                        'pool.dataset.update_impl',
                        UpdateImplArgs(name=dataset, zprops=update_props),
                    )

        return list(datasets.values())

    @private
    def mount_system_dataset(self, datasets, target_path=SYSDATASET_PATH):
        """Mount the system dataset hierarchy at `target_path` and run
        post-mount actions for each dataset (create_paths, post_mount_actions).
        """
        target_fd = os.open(target_path, os.O_DIRECTORY)
        try:
            mount_hierarchy(target_fd=target_fd, datasets=datasets)
        finally:
            os.close(target_fd)
        self._finalize_datasets(datasets)

    @private
    def migrate(self, _from, _to):
        """Migrate the system dataset from `_from` to `_to`.

        With no source: just create + mount at SYSDATASET_PATH.

        With a source:
        - Wipe any leftover at `{_to}/.system` so receive lands clean.
        - Replicate via lzc.send | lzc.receive (source stays live).
        - Run setup_datasets to create any spec entries the source didn't
          have and reconcile property drift.
        - Mount the populated tree under a tmpdir on /var/db (so the
          staging mount inherits MS_PRIVATE from /var, required for
          MOVE_MOUNT_BENEATH).
        - Quiesce daemons, drop the cores→coredump bind, and atomically
          swap the staged tree under SYSDATASET_PATH.
        - Run finalize and destroy the old pool's datasets.
        """
        config = self.middleware.call_sync('systemdataset.config')
        os.makedirs(SYSDATASET_PATH, mode=0o755, exist_ok=True)

        if not _from:
            datasets = self.middleware.call_sync(
                'systemdataset.setup_datasets', _to, config['uuid'],
            )
            self.mount_system_dataset(datasets)
            self._post_mount_setup()
            return

        # Wipe any leftover at the destination so receive lands on a
        # clean slate. The dataset not existing (first migration to this
        # pool) is the expected case; any other error here means the pool
        # is unhealthy and we should not blindly proceed to replicate
        # over it. bypass=True because <pool>/.system is on the protected
        # paths list — we're a legitimate internal caller.
        with suppress(ZFSPathNotFoundException):
            self.call_sync2(
                self.s.zfs.resource.destroy_impl, f'{_to}/.system',
                recursive=True, bypass=True,
            )

        replicate(_from, _to, config['uuid'])

        datasets = self.middleware.call_sync(
            'systemdataset.setup_datasets', _to, config['uuid'],
        )

        # Stage on /var/db so the new mounts inherit MS_PRIVATE (set on
        # /var at boot) — MOVE_MOUNT_BENEATH requires the source mount to
        # be MS_PRIVATE or it returns EINVAL.
        with tempfile.TemporaryDirectory(prefix='/var/db/', ignore_cleanup_errors=True) as staging:
            target_fd = os.open(staging, os.O_DIRECTORY)
            try:
                os.fchmod(target_fd, 0o755)
                mount_hierarchy(target_fd=target_fd, datasets=datasets)
            finally:
                os.close(target_fd)

            with self.release_system_dataset():
                # Drop the cores → coredump bind before recycling
                # SYSDATASET_PATH/cores; _post_mount_setup re-binds.
                with suppress(OSError, ValueError):
                    umount(_COREDUMP_PATH)
                swap_under(staging, SYSDATASET_PATH)

            # Belt-and-braces: if swap_under failed mid-flight, the
            # staging mount may still exist. Clean it up.
            stat = truenas_os.statx(
                path=staging,
                mask=truenas_os.STATX_MNT_ID_UNIQUE | truenas_os.STATX_BASIC_STATS,
            )
            if stat.stx_attributes & truenas_os.STATX_ATTR_MOUNT_ROOT:
                umount(staging, force=True, recursive=True)

        self._finalize_datasets(datasets)
        self._post_mount_setup()

        try:
            self.call_sync2(
                self.s.zfs.resource.destroy_impl, f'{_from}/.system',
                recursive=True, bypass=True,
            )
        except Exception:
            self.logger.warning(
                'Failed to destroy old system datasets on %r', _from, exc_info=True,
            )

    @contextmanager
    @private
    def release_system_dataset(self):
        """Quiesce daemons that hold sysdataset handles.

        sysdataset.update and sysdataset.setup can both reach this via
        different code paths — the lock prevents simultaneous releases.
        """
        with self.sysdataset_release_lock:
            restart = ['netdata']
            if self.middleware.call_sync('service.started', 'nfs'):
                restart.append('nfs')
            if self.middleware.call_sync('service.started', 'open-vm-tools'):
                restart.append('open-vm-tools')

            try:
                for svc in restart:
                    self.middleware.call_sync('service.control', 'STOP', svc).wait_sync(raise_error=True)
                close_sysdataset_tdb_handles()
                yield
            finally:
                for svc in reversed(restart):
                    self.middleware.call_sync('service.control', 'START', svc).wait_sync(raise_error=True)

    @private
    def get_system_dataset_spec(self, pool, uid):
        return get_system_dataset_spec(pool, uid)

    # ---- internals ---------------------------------------------------------

    def _finalize_datasets(self, datasets: list[dict]) -> None:
        """Run create_paths and post_mount_actions for each dataset spec."""
        for ds in datasets:
            for cp in ds.get('create_paths', []):
                try:
                    os.makedirs(cp['path'], exist_ok=True)
                    st = os.stat(cp['path'])
                    uid, gid = cp.get('uid'), cp.get('gid')
                    if uid is not None and gid is not None and (st.st_uid != uid or st.st_gid != gid):
                        os.chown(cp['path'], uid, gid)
                    if (mode := cp.get('mode')) and (st.st_mode & 0o777) != mode:
                        os.chmod(cp['path'], mode)
                except Exception:
                    self.logger.exception(
                        'Failed to ensure %r path for %r dataset', cp['path'], ds['name'],
                    )
            for action in ds.get('post_mount_actions', []):
                try:
                    self.middleware.call_sync(action['method'], *action.get('args', []))
                except Exception:
                    self.logger.error(
                        'Failed to run post mount action %r for %r dataset',
                        action['method'], ds['name'], exc_info=True,
                    )

    def _post_mount_setup(self) -> None:
        """Post-mount fixups: enforce acltype=off, (re)bind cores → coredump.

        Runs after the system dataset is mounted at SYSDATASET_PATH (whether
        via fresh mount or migration swap). Idempotent.
        """
        config = self.middleware.call_sync('systemdataset.config')
        try:
            sysds_mntinfo = statmount(path=SYSDATASET_PATH)
        except FileNotFoundError:
            raise CallError(f'{SYSDATASET_PATH}: not mounted after setup')
        if sysds_mntinfo['mount_source'] != config['basename']:
            raise CallError(
                f'{SYSDATASET_PATH}: expected {config["basename"]!r}, '
                f'got {sysds_mntinfo["mount_source"]!r}',
            )

        # System dataset must be a plain legacy mount — kill any ACL state.
        if 'POSIXACL' in sysds_mntinfo['super_opts'] or 'NFSV4ACL' in sysds_mntinfo['super_opts']:
            self.middleware.call_sync(
                'pool.dataset.update_impl',
                UpdateImplArgs(name=config['basename'], zprops={'acltype': 'off'}),
            )

        self._bind_cores_to_coredump()

    def _bind_cores_to_coredump(self) -> None:
        """Bind <SYSDATASET>/cores onto /var/lib/systemd/coredump.

        On a `run_migration` boot the cores directory is wiped first
        (stale coredumps from before an upgrade are uninteresting and can
        be large).

        If the destination is already a mountpoint (a previous setup
        bound it), we use MOVE_MOUNT_BENEATH to layer the new bind under
        the old one, then unmount the old top to expose the new — same
        atomic pattern as the sysdataset swap.
        """
        corepath = f'{SYSDATASET_PATH}/cores'
        if not os.path.exists(corepath):
            return

        if self.call_sync2(self.s.keyvalue.get, 'run_migration', False):
            try:
                for f in Path(corepath).iterdir():
                    f.unlink()
            except Exception:
                self.logger.warning('Failed to clear old core files.', exc_info=True)

        os.makedirs(_COREDUMP_PATH, exist_ok=True)
        st = truenas_os.statx(path=_COREDUMP_PATH, mask=truenas_os.STATX_BASIC_STATS)
        is_mountpoint = bool(st.stx_attributes & truenas_os.STATX_ATTR_MOUNT_ROOT)

        # Clone the cores mount (it stays at corepath) and attach the
        # clone at coredump_path, beneath the existing mount if any.
        tree_fd = truenas_os.open_tree(
            path=corepath,
            flags=truenas_os.OPEN_TREE_CLONE | truenas_os.OPEN_TREE_CLOEXEC,
        )
        try:
            move_flags = truenas_os.MOVE_MOUNT_F_EMPTY_PATH
            if is_mountpoint:
                move_flags |= truenas_os.MOVE_MOUNT_BENEATH
            truenas_os.move_mount(
                from_dirfd=tree_fd, from_path='',
                to_path=_COREDUMP_PATH,
                flags=move_flags,
            )
        finally:
            os.close(tree_fd)

        if is_mountpoint:
            umount(_COREDUMP_PATH, force=True, recursive=True)


async def pool_post_create(middleware, pool):
    if (await middleware.call('systemdataset.config'))['pool'] == await middleware.call('boot.pool_name'):
        await middleware.call('systemdataset.setup')


async def pool_post_import(middleware, pool):
    """On pool import we may need to reconfigure the system dataset."""
    await middleware.call('systemdataset.setup')


async def pool_pre_export(middleware, pool, options, job):
    sysds = await middleware.call('systemdataset.config')
    if sysds['pool'] == pool:
        job.set_progress(40, 'Reconfiguring system dataset')
        sysds_job = await middleware.call('systemdataset.update', {
            'pool': None, 'pool_exclude': pool,
        })
        await sysds_job.wait()
        if sysds_job.error:
            raise CallError(
                f'This pool contains system dataset, but its reconfiguration failed: {sysds_job.error}',
            )


async def setup(middleware):
    def setup_paths():
        # Make /var private so our mount churn (sysdataset migrate, the
        # cores→coredump bind, future share rebinds) does not propagate
        # to peer namespaces (systemd unit private mounts, container
        # namespaces, etc.). Default systemd makes / shared, so /var
        # inherits MS_SHARED — under MS_SHARED our move_mount events get
        # replicated into peers, and open_tree(CLONE) carries the source's
        # peer group into the clone (the cores bind today is therefore in
        # the same peer group as /var/db/system/cores; a stray umount of
        # /var/lib/systemd/coredump would propagate to /var/db/system/cores).
        # MS_PRIVATE on /var fixes both. Required for MOVE_MOUNT_BENEATH
        # too — that flag rejects non-private source mounts.
        truenas_os.mount_setattr(
            path='/var',
            propagation=truenas_os.MS_PRIVATE,
            flags=truenas_os.AT_RECURSIVE,
        )

        os.makedirs(SYSDATASET_PATH, mode=0o755, exist_ok=True)
        if not os.path.exists('/var/cache/nscd') or not os.path.islink('/var/cache/nscd'):
            if os.path.exists('/var/cache/nscd'):
                shutil.rmtree('/var/cache/nscd')
            os.makedirs('/var/run/nscd/cache', exist_ok=True)
        if not os.path.islink('/var/cache/nscd'):
            os.symlink('/var/run/nscd/cache', '/var/cache/nscd')

    middleware.register_hook('pool.post_create', pool_post_create)
    # Reconfigure the system dataset first thing after a pool import.
    middleware.register_hook('pool.post_import', pool_post_import, order=-10000)
    middleware.register_hook('pool.pre_export', pool_pre_export, order=40, raise_error=True)

    try:
        await middleware.run_in_thread(setup_paths)
    except Exception:
        middleware.logger.error('Error moving cache away from boot pool', exc_info=True)
