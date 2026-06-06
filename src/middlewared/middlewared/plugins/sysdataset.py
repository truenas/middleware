"""System dataset.

The system dataset is a hierarchy of ZFS datasets rooted at <pool>/.system

Mount + replication primitives live in `system_dataset.mount`. This module
is the orchestrator: pool selection, DB persistence, and the state machine
that decides what to do when configured pool, on-disk reality, and live
mount disagree.


============================================================================
Terminology
============================================================================

    configured_pool   The user's recorded selection
                      (`system_systemdataset.sys_pool`). Empty string means
                      "no preference" -- config_extend resolves it to the
                      boot pool for display, but the field stays empty in
                      the DB so a real selection can be distinguished from
                      a default.

    live_pool         The pool whose `<pool>/.system` is currently mounted
                      at SYSDATASET_PATH (/var/db/system), determined by
                      statmount. None if nothing is mounted there. May
                      differ from configured_pool for legitimate reasons
                      (fallback overlay) or pathological ones (a prior
                      migration crashed between DB write and mount swap).

    target_pool       The pool reconcile() will leave live at the end of
                      this call.
                      - In setup() / pool.post_* flows: selected from
                        configured_pool via pool-availability fallback
                        rules (see "Pool selection" below).
                      - In do_update flow: the user-validated choice
                        (already known available; no fallback needed).

    authority         When live_pool != target_pool, whose data wins
                      (the SysdatasetAuthority enum):
                        LIVE    -> live_pool's contents must be preserved
                                  (snapshot + send -> target_pool).
                                  Set by do_update -- the user is moving
                                  their selection; the data they were
                                  using has to travel with them.
                        TARGET  -> target_pool's existing `.system` is the
                                  truth; live_pool was a transient
                                  overlay. Set by setup() -- the DB hasn't
                                  changed, so a live mismatch is the
                                  thing to discard.

                      reconcile() promotes TARGET -> LIVE when it
                      itself persists a fresh non-fallback selection
                      (e.g. pool.post_create chose a data pool against
                      an empty DB). In that case we are effectively
                      acting on the user's behalf, and the data they
                      can currently see at SYSDATASET_PATH must follow
                      the selection.

    force_pool        Process-local override that makes config_extend
                      report `target_pool` for the duration of a fallback
                      overlay without persisting that choice. Cleared at
                      the start of every reconcile().


============================================================================
Pool selection (setup() path only -- do_update validates upfront)
============================================================================

select_system_dataset_pool(configured_pool, exclude_pool) resolves the DB
value against pool reality:

    configured_pool        pool state                       -> result
    ----------------------------------------------------------------------
    (unset / empty)        any                              -> first usable
                                                              non-boot pool,
                                                              else boot.
                                                              persisted.
    configured             importable, not key-locked       -> configured.
    configured             passphrase-locked root           -> configured.
                                                              (sysdataset
                                                              uses legacy
                                                              mount; per-
                                                              dataset keys
                                                              are independent
                                                              of root state.)
    configured             root locked-with-key             -> boot,
                                                              force_pool=boot
                                                              (overlay; DB
                                                              unchanged so
                                                              we revisit
                                                              when it
                                                              unlocks).
    configured             not imported                     -> boot,
                                                              force_pool=boot
                                                              (overlay).

`is_fallback` is True in the two overlay rows. The DB is only rewritten in
the first row.


============================================================================
Reconcile state machine
============================================================================

Once target_pool and authority are settled, reconcile() inspects live_pool
and picks one of four actions:

    live_pool   live==target   authority   action
    ----------------------------------------------------------------------
    None        any            any         MOUNT_FRESH
    target      yes            any         RECONCILE_ONLY
    other       no             LIVE        MIGRATE_DATA
    other       no             TARGET      ABANDON_AND_REMOUNT

Action semantics:

    MOUNT_FRESH
        Nothing mounted at SYSDATASET_PATH. Create any missing datasets
        under <target_pool>/.system per the spec, mount the hierarchy,
        finalize. Used at first boot and after a `pool_pre_export` cleared
        the field with no live mount left behind.

    RECONCILE_ONLY
        Already mounted from the right pool. Re-run setup_datasets
        (idempotent -- creates anything missing, fixes prop drift) and
        post-mount fixups (acltype=off, cores->coredump bind). No mount
        churn, no service quiesce.

    MIGRATE_DATA
        Snapshot live_pool/.system recursively, send to target_pool/.system
        via local_replicate with `force=True` (zfs receive -F), then (with
        daemon quiesce) umount SYSDATASET_PATH and mount target_pool/.system
        there, and destroy live_pool/.system. Force receive replaces any pre-existing
        `<target>/.system` atomically as part of the receive -- stale
        leftovers from prior aborted migrations and child datasets not
        in the stream get destroyed by the kernel during recv.

        Some destinations the kernel refuses to overwrite even with -F
        (top-level snapshots, clones). In those cases the receive fails
        with EZFS_EXISTS; we fall back to an explicit recursive destroy
        of `<target>/.system` (with hard return-value checking, since
        destroy_impl reports logical failures via tuple return rather
        than raising) and retry the receive once.

    ABANDON_AND_REMOUNT
        With daemon quiesce, umount SYSDATASET_PATH and mount target_pool's
        existing `.system` there. live_pool's data is discarded (it was an
        overlay or a stale leftover; the user-visible "real" data lives on
        target_pool). No destroy of target, no replication.


============================================================================
Caller -> action flowchart
============================================================================

    setup()  /  pool.post_create  /  pool.post_import  /  failover event
        |
        |   exclude_pool=None (or the pool being processed)
        |   authority=TARGET   <- DB is source of truth
        v
    reconcile() --> select target via fallback rules
                 --> persist target to DB if it's a non-fallback change
                 --> state machine above

    do_update({pool, pool_exclude})           (job, lock=sysdataset_update)
        |
        +-> _validate_and_select_pool   (verrors if pool unavailable)
        +-> write target to DB
        +-> reconcile(authority=LIVE)
        |       target = DB value (just written)
        |       authority=LIVE -> user-initiated; preserve current data
        +-> return config

    pool.pre_export(pool_being_exported)
        |
        +-> systemdataset.update({pool: None, pool_exclude: <being-exported>})
              |
              +-> _validate_and_select_pool picks the next data pool
                  (or '' for boot fallback) and the rest is do_update.

The two paths converge on reconcile(); the only difference is the
`authority` parameter -- i.e. who owns the data when they disagree.


============================================================================
HA lifecycle
============================================================================

In a TrueNAS HA pair the data pool that hosts the sysdataset is shared
storage imported by exactly one controller at a time. The standby
controller cannot import that pool, so the sysdataset must live somewhere
else for the duration. The boot-pool overlay handles this naturally:

    Standby controller, DB says "tank" (the shared pool):
        select_system_dataset_pool(preferred="tank")
          -> tank not importable here  -> (boot, is_fallback=True)
        force_pool = boot (no DB write; the configured choice is unchanged)
        live = None at boot, or boot from a prior reconcile
          -> MOUNT_FRESH or RECONCILE_ONLY on the boot overlay.

    Failover: standby takes over and imports tank. pool.post_import
    fires setup() -> reconcile(authority=TARGET):
        select_system_dataset_pool(preferred="tank")
          -> tank now importable  -> (tank, is_fallback=False)
        force_pool cleared; config['pool'] == DB's "tank"; no drift.
        live = boot (the overlay), target = tank, authority = TARGET
          -> ABANDON_AND_REMOUNT mounts tank/.system from the shared pool.
        The boot-pool overlay is discarded: its contents were standby-
        local scratch, not real sysdataset state. The "real" sysdataset
        lives on tank with whatever the previously-active controller
        wrote into it.

    Failback (planned takeover the other direction) is symmetric: the
    incoming-active sees pool.post_import on tank, runs the same
    ABANDON_AND_REMOUNT, and the now-standby falls back to its own boot
    overlay on the next setup() pass.

The authority=TARGET choice on the failover path is the load-bearing
piece: copying the standby's boot-pool overlay onto tank would destroy
the active's working state. That's exactly the "target wins" semantic
ABANDON_AND_REMOUNT implements.

Per-controller UUID handling (sys_uuid_b column, ensure_standby_uuid)
sits outside reconcile() -- each controller has its own uuid, synced
once over `failover.call_remote`.
"""
from contextlib import contextmanager, suppress
import enum
import errno
import os
import shutil
import stat
import threading
import uuid

import truenas_os
from truenas_os_pyutils.mount import iter_mountinfo, statmount, umount
import truenas_pylibzfs

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
from middlewared.plugins.system_dataset.hierarchy import SystemDatasetZfsProperties, get_system_dataset_spec
from middlewared.plugins.system_dataset.mount import (
    mount_hierarchy,
    replicate,
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


class SysdatasetAuthority(enum.StrEnum):
    """Whose data wins when the live mount and the target pool disagree.

    LIVE    the data currently visible at SYSDATASET_PATH is authoritative
            and must travel to the target pool. Set by do_update -- the user
            is moving their selection and their data has to follow.
    TARGET  the target pool's existing `.system` is authoritative; whatever
            is mounted now was a transient overlay and is discarded. Set by
            setup() -- the DB hasn't changed, so a live mismatch is the thing
            to throw away.
    """
    LIVE = 'LIVE'
    TARGET = 'TARGET'


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
    sysdataset_reconcile_lock = threading.Lock()

    @private
    def sysdataset_path(self, expected_datasetname=None):
        """
        This function returns either None or SYSDATASET_PATH,
        and is called potentially quite frequently (once per ZFS event
        or pool.dataset.query, etc).

        `None` indicates that there was an issue with filesystem mounted
        at SYSDATASET_PATH. Typically this could indicate a failed migration
        of system dataset or problem importing expected pool for system dataset.
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
        # Treat empty system dataset pool as boot pool
        config['pool_set'] = bool(config['pool'])
        config['pool'] = self.force_pool or config['pool'] or await self.middleware.call('boot.pool_name')
        config['basename'] = f'{config["pool"]}/.system'

        # Make `uuid` point to the uuid of current node
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
        """
        Retrieve pool choices which can be used for configuring system dataset.
        """
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

        Set `pool` to choose which pool hosts the system dataset. Changing the
        pool moves the system dataset and its contents to the new pool.
        """
        job.set_progress(0, 'Validating system dataset configuration')
        data.setdefault('pool_exclude', None)
        config = await self.config()
        new_pool = await self._validate_and_select_pool(data, config)

        await self.middleware.call(
            'datastore.update', 'system.systemdataset', config['id'],
            {'pool': new_pool or ''}, {'prefix': 'sys_'},
        )

        await self.middleware.call(
            'systemdataset.reconcile', data['pool_exclude'], SysdatasetAuthority.LIVE, job,
        )
        job.set_progress(100, 'System dataset configuration complete')
        return await self.config()

    async def _validate_and_select_pool(self, data, config):
        """Validate the requested pool and return the pool name to record.

        If the caller explicitly passes pool=None (e.g. pool_pre_export
        clearing the selection), pick the first usable data pool that
        isn't excluded. Returning '' lets the DB record the empty value
        and config_extend fall back to the boot pool.
        """
        verrors = ValidationErrors()
        new_pool = data.get('pool', config['pool'])

        if new_pool and new_pool != config['pool']:
            if error := await self.destination_pool_error(new_pool):
                verrors.add('sysdataset_update.pool', error)

        if new_pool:
            if new_pool not in await self.pool_choices(False):
                verrors.add(
                    'sysdataset_update.pool',
                    'The system dataset cannot be placed on this pool.',
                )
        else:
            # Caller passed None -- pick a data pool ourselves so that
            # do_update has a concrete `new_pool` to migrate to.
            for pool in await self.middleware.call(
                'systemdataset.query_pools_for_system_dataset', data['pool_exclude'],
            ):
                if await self.destination_pool_error(pool):
                    continue
                new_pool = pool
                break
            else:
                # No usable data pool -- clear the field so config_extend
                # falls back to the boot pool.
                new_pool = ''

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
        # 1.1 is a safety margin because same files won't
        # take exactly the same amount of space on a different pool
        used = int(used * 1.1)
        if available < used:
            return (
                f'Insufficient disk space available on {new_pool} ({format_size(available)}). '
                f'Need {format_size(used)}'
            )

    @private
    def setup(self, exclude_pool: str | None = None):
        """Reconcile with DB as the source of truth (SysdatasetAuthority.TARGET).

        Public entry point used by `pool.post_create`, `pool.post_import`,
        and failover events. do_update goes directly to reconcile().
        """
        return self.reconcile(exclude_pool, SysdatasetAuthority.TARGET)

    @private
    def reconcile(self, exclude_pool: str | None, authority: SysdatasetAuthority, job=None):
        """Bring SYSDATASET_PATH to a known-good state.

        See the module docstring for the state matrix. This is the single
        dispatcher used by both `setup` (SysdatasetAuthority.TARGET) and
        `do_update` (SysdatasetAuthority.LIVE).

        `job`, when supplied (do_update path), is threaded down to the
        reconcile action so it can report progress. setup()/failover
        reconciles pass None and report nothing.

        Fires the `sysdataset.setup` hook around the work so subscribers
        (e.g. failover state UI) see exactly one in_progress=True / =False
        pair per reconcile.

        Serialized by `sysdataset_reconcile_lock` so concurrent callers
        (do_update, setup from pool hooks, failover) can never swap the
        SYSDATASET_PATH mount at the same time.
        """
        try:
            authority = SysdatasetAuthority(authority)
        except ValueError:
            raise CallError(f'invalid authority: {authority!r}')

        # Serialize every reconcile regardless of caller -- do_update holds the
        # sysdataset_update job lock, but setup() (pool.post_create/post_import,
        # failover) holds nothing. Without this, two reconciles could swap the
        # /var/db/system mount concurrently. Plain (non-reentrant) Lock is
        # deliberate: nothing run under it re-enters reconcile/setup/update, so a
        # future change that does will deadlock loudly in testing instead of
        # silently allowing a concurrent mount swap. Do NOT switch to RLock.
        with self.sysdataset_reconcile_lock:
            self.middleware.call_hook_sync('sysdataset.setup', data={'in_progress': True})
            try:
                self._reconcile_impl(exclude_pool, authority, job)
            finally:
                self.middleware.call_hook_sync('sysdataset.setup', data={'in_progress': False})
            return self.middleware.call_sync('systemdataset.config')

    def _reconcile_impl(self, exclude_pool, authority, job=None):
        # 1. Pick target_pool and decide whether the DB needs persistence
        #    or an overlay. See "Pool selection" in the module docstring.
        self.force_pool = None
        preferred = self.middleware.call_sync(
            'datastore.config', 'system_systemdataset',
        )['sys_pool']
        target_pool, is_fallback = self.select_system_dataset_pool(
            preferred_pool=preferred, exclude_pool=exclude_pool,
        )

        config = self.middleware.call_sync('systemdataset.config')
        if is_fallback:
            self.force_pool = target_pool
            config = self.middleware.call_sync('systemdataset.config')
        elif target_pool != config['pool']:
            # Non-fallback drift: we're making a selection on the user's
            # behalf (e.g. pool_post_create on a DB that had no pool
            # picked yet). Persist directly -- we can't re-enter
            # systemdataset.update from here because do_update holds the
            # sysdataset_update job lock.
            #
            # Promote authority to SysdatasetAuthority.LIVE: the data the user can see
            # at SYSDATASET_PATH right now (typically the boot-pool
            # fallback) is the truth and must travel to target_pool.
            self.logger.debug(
                'Updating system dataset pool from %r to %r', config['pool'], target_pool,
            )
            self.middleware.call_sync(
                'datastore.update', 'system.systemdataset', config['id'],
                {'pool': target_pool}, {'prefix': 'sys_'},
            )
            config = self.middleware.call_sync('systemdataset.config')
            authority = SysdatasetAuthority.LIVE

        # 2. Make sure SYSDATASET_PATH is a real directory before any mount
        #    work. Remove whatever's there if it isn't one (stale file or
        #    symlink), then create it.
        try:
            if not stat.S_ISDIR(os.lstat(SYSDATASET_PATH).st_mode):
                os.unlink(SYSDATASET_PATH)
        except FileNotFoundError:
            pass
        os.makedirs(SYSDATASET_PATH, mode=0o755, exist_ok=True)

        # 3. Inspect live state and dispatch via the state machine.
        live_pool = self._live_pool()

        if live_pool is None:
            self._action_mount_fresh(target_pool, config['uuid'], job)
        elif live_pool == target_pool:
            self._action_reconcile_only(target_pool, config['uuid'], job)
        elif authority == SysdatasetAuthority.LIVE:
            self.logger.debug(
                'Migrating system dataset from %r to %r', live_pool, target_pool,
            )
            self._action_migrate_data(live_pool, target_pool, config['uuid'], job)
        else:
            self.logger.info(
                'Abandoning sysdataset mount on %r in favor of %r (no data copy)',
                live_pool, target_pool,
            )
            self._action_abandon_and_remount(target_pool, config['uuid'], job)

    @private
    def _live_pool(self):
        """Pool whose `<pool>/.system` is mounted at SYSDATASET_PATH.

        Returns None if nothing is mounted or the mount source doesn't
        match the `<pool>/.system` pattern (e.g. a tmpfs slipped under
        the path somehow -- treat as "nothing useful is there").
        """
        try:
            mntinfo = statmount(path=SYSDATASET_PATH)
        except FileNotFoundError:
            return None

        mount_source = mntinfo['mount_source'] or ''
        if not mount_source.endswith('/.system'):
            return None
        return mount_source.split('/', 1)[0]

    @private
    def query_pools_for_system_dataset(self, exclude_pool=None):
        """
        Pools with passphrase-locked root level datasets are permitted as system
        dataset targets. This is because ZFS encryption is at the dataset level
        rather than pool level, and we use a legacy mount for the system dataset.
        Key format is only exposed via libzfs and so reading mountinfo here is
        insufficient.
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

        # Not mounted -- check whether the root is locked-with-key.
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
                    properties=['encryption', 'quota', 'used'] + list(SystemDatasetZfsProperties)
                ),
            )
        }
        for dataset, config in datasets.items():
            props = config['props']
            # Disable encryption for system managed datasets that are
            # configured on zpools that are passphrase-encrypted.
            if root_dataset_is_passphrase_encrypted:
                props['encryption'] = 'off'
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
                # property-specific translation (e.g. raw "on" -> True).
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
    def mount_system_dataset(self, datasets):
        """Mount the system dataset hierarchy at SYSDATASET_PATH."""
        target_fd = os.open(SYSDATASET_PATH, os.O_DIRECTORY)
        try:
            mount_hierarchy(target_fd=target_fd, datasets=datasets)
        finally:
            os.close(target_fd)

    def _finalize_mount(self, datasets):
        """Post-mount steps shared by every reconcile action: per-dataset
        create_paths / post_mount_actions, then acltype + cores->coredump bind.
        """
        self._finalize_datasets(datasets)
        self._post_mount_setup()

    @staticmethod
    def _job_progress(job, percent, description):
        """Report reconcile progress when a job is driving it.

        do_update forwards its job down here; setup()/failover reconciles
        pass job=None and report nothing.
        """
        if job is not None:
            job.set_progress(percent, description)

    # --- reconcile actions ----------------------------------------------
    # The four helpers below are the action vocabulary for reconcile().
    # All are idempotent and assume SYSDATASET_PATH already exists as a
    # real directory (verified in _reconcile_impl). Each takes an optional
    # `job` (do_update path) to report progress; setup() passes None.

    def _action_mount_fresh(self, target_pool, uid, job=None):
        """MOUNT_FRESH: nothing live, mount target_pool from scratch."""
        self._job_progress(job, 30, f'Configuring system dataset on {target_pool!r}')
        datasets = self.middleware.call_sync(
            'systemdataset.setup_datasets', target_pool, uid,
        )
        self._job_progress(job, 70, f'Mounting system dataset on {target_pool!r}')
        self.mount_system_dataset(datasets)
        self._job_progress(job, 90, 'Finalizing system dataset configuration')
        self._finalize_mount(datasets)

    def _action_reconcile_only(self, target_pool, uid, job=None):
        """RECONCILE_ONLY: already correctly mounted, just ensure spec
        and post-mount fixups. No mount churn, no service quiesce.
        """
        self._job_progress(job, 40, f'Reconciling system dataset on {target_pool!r}')
        datasets = self.middleware.call_sync(
            'systemdataset.setup_datasets', target_pool, uid,
        )
        self._job_progress(job, 90, 'Finalizing system dataset configuration')
        self._finalize_mount(datasets)

    def _action_migrate_data(self, live_pool, target_pool, uid, job=None):
        """MIGRATE_DATA: send live -> target and swap the mount, then destroy
        live. The send and the swap run under one quiesce, so the copy is taken
        from a quiescent source and the umount -> mount window is covered.

        Receive strategy:
        - Try `force=True` (zfs receive -F) first. For a recursive stream
          the kernel replaces `{target_pool}/.system` atomically as part
          of the receive, destroying children and snapshots on dest that
          aren't in the stream.
        - libzfs refuses -F when the dest has top-level snapshots or is
          a clone (EZFS_EXISTS). In that case, recursive-destroy the dest
          (hard-failing if destroy_impl reports a logical error, since
          retrying without the dataset gone is pointless) and replicate
          again.
        """
        # Set before entering the CM -- release_system_dataset() stops the
        # services as its first act, so the message is live while it does.
        self._job_progress(job, 10, 'Stopping services that use the system dataset')
        with self.release_system_dataset():
            self._job_progress(job, 25, f'Copying system dataset to {target_pool!r}')
            try:
                replicate(live_pool, target_pool)
            except truenas_pylibzfs.ZFSException as e:
                if e.code != truenas_pylibzfs.ZFSError.EZFS_EXISTS:
                    raise
                self.logger.warning(
                    '%s/.system: force receive blocked by existing snapshots '
                    'or clones; falling back to recursive destroy + retry',
                    target_pool,
                )
                self._destroy_sysdataset_root(target_pool, must_succeed=True)
                replicate(live_pool, target_pool)

            self._job_progress(job, 70, f'Configuring system dataset on {target_pool!r}')
            datasets = self.middleware.call_sync(
                'systemdataset.setup_datasets', target_pool, uid,
            )
            self._job_progress(job, 80, f'Mounting system dataset on {target_pool!r}')
            self._swap(datasets)
            # Last act inside the CM: the restart happens on exit, so this
            # message is what's shown while the services come back up.
            self._job_progress(job, 85, 'Restarting services')

        self._job_progress(job, 90, 'Finalizing system dataset configuration')
        self._finalize_mount(datasets)

        # Drop the source. The data has moved to target_pool, so
        # live_pool/.system has no live consumers. Best-effort: a stuck
        # destroy here must not undo the migration -- log and leave the orphan.
        self._job_progress(job, 95, f'Removing previous system dataset from {live_pool!r}')
        self._destroy_sysdataset_root(live_pool, must_succeed=False)

    def _destroy_sysdataset_root(self, pool, *, must_succeed):
        """Recursively destroy `<pool>/.system` with explicit status
        handling.

        destroy_impl reports logical failures via `(failed_msg, errnum)`
        without raising, so the result has to be checked. `ZFSPathNotFoundException`
        ("nothing to do") is always benign.

        must_succeed=True raises CallError on any failure -- used by the
        MIGRATE_DATA fallback where leaving the dataset behind would
        guarantee the retry hits EZFS_EXISTS again.

        must_succeed=False logs a warning and returns -- used by the
        post-migration source cleanup, where the migration has already
        succeeded and a leftover .system on the source pool is
        recoverable out of band.
        """
        path = f'{pool}/.system'
        try:
            failed, errnum = self.call_sync2(
                self.s.zfs.resource.destroy_impl, path,
                recursive=True, bypass=True,
            )
        except ZFSPathNotFoundException:
            return
        except Exception:
            if must_succeed:
                raise
            self.logger.warning('%s: destroy raised', path, exc_info=True)
            return

        if not failed:
            return
        msg = f'{path}: recursive destroy failed: {failed} (errno={errnum})'
        if must_succeed:
            raise CallError(msg, errno=errnum or errno.EIO)
        self.logger.warning(msg)

    def _action_abandon_and_remount(self, target_pool, uid, job=None):
        """ABANDON_AND_REMOUNT: mount target's existing .system over the
        current live mount. NO destroy of target_pool/.system, NO data
        copy -- the live mount is treated as an overlay to discard.
        """
        self._job_progress(job, 30, f'Configuring system dataset on {target_pool!r}')
        datasets = self.middleware.call_sync(
            'systemdataset.setup_datasets', target_pool, uid,
        )
        self._job_progress(job, 50, 'Stopping services that use the system dataset')
        with self.release_system_dataset():
            self._job_progress(job, 75, f'Mounting system dataset on {target_pool!r}')
            self._swap(datasets)
            self._job_progress(job, 85, 'Restarting services')
        self._job_progress(job, 90, 'Finalizing system dataset configuration')
        self._finalize_mount(datasets)

    def _swap(self, datasets):
        """Replace the system dataset mounted at SYSDATASET_PATH with `datasets`:
        recursively umount the old tree, then mount the new one at the final
        path. The recursive umount propagates (shared /var) into the mount
        namespaces of sandboxed services that cloned /var/db/system, releasing
        their copies so the source datasets are destroyable. Must run inside
        release_system_dataset() -- the caller quiesces the daemons that hold
        handles for the umount -> mount window.
        """
        # Drop the cores -> coredump bind; _post_mount_setup re-binds it.
        with suppress(OSError, ValueError):
            umount(_COREDUMP_PATH)
        self._umount_sysdataset()
        self.mount_system_dataset(datasets)

    def _umount_sysdataset(self):
        """Recursively umount SYSDATASET_PATH. Plain umount first so a real
        local holder surfaces and is logged; lazy (MNT_DETACH) retry if one is
        busy so the swap still proceeds.
        """
        try:
            umount(SYSDATASET_PATH, recursive=True)
        except OSError:
            procs = self.middleware.call_sync(
                'pool.dataset.processes_using_paths', [SYSDATASET_PATH], True, True,
            )
            self.logger.warning(
                '%s: busy during swap (%r); falling back to lazy umount',
                SYSDATASET_PATH, procs,
            )
            umount(SYSDATASET_PATH, recursive=True, detach=True)

    @contextmanager
    @private
    def release_system_dataset(self):
        """
        This context manager is used to toggle system-dataset dependent services and
        tasks for cases where the dataset is unmounted / remounted.

        Callers run inside reconcile(), which holds sysdataset_reconcile_lock, so
        releases are already serialized -- no separate lock is needed here.
        """
        # TODO: Review these services because /var/log no longer sits on
        # the system dataset so any service that could potentially open
        # a file descriptor underneath /var/log will no longer need to be
        # stopped/restarted to allow the system dataset to migrate
        restart = ['netdata', 'truenas_zfstierd']
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
        """Post-mount fixups: enforce acltype=off, (re)bind cores -> coredump.

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

        # System dataset must be a plain legacy mount -- kill any ACL state.
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

        If the destination is already a mountpoint, unmount it first so the
        fresh clone lands on a bare dir.
        """
        corepath = f'{SYSDATASET_PATH}/cores'
        if not os.path.exists(corepath):
            return

        if self.call_sync2(self.s.keyvalue.get, 'run_migration', False):
            try:
                with os.scandir(corepath) as it:
                    for entry in it:
                        os.unlink(entry.path)
            except Exception:
                self.logger.warning('Failed to clear old core files.', exc_info=True)

        os.makedirs(_COREDUMP_PATH, exist_ok=True)
        # Drop any prior bind so the fresh clone lands on a bare dir.
        with suppress(OSError):
            umount(_COREDUMP_PATH)

        # Clone the cores mount (it stays at corepath) and attach the clone
        # at coredump_path.
        tree_fd = truenas_os.open_tree(
            path=corepath,
            flags=truenas_os.OPEN_TREE_CLONE | truenas_os.OPEN_TREE_CLOEXEC,
        )
        try:
            truenas_os.move_mount(
                from_dirfd=tree_fd, from_path='',
                to_path=_COREDUMP_PATH,
                flags=truenas_os.MOVE_MOUNT_F_EMPTY_PATH,
            )
        finally:
            os.close(tree_fd)


async def pool_post_create(middleware, pool):
    if (await middleware.call('systemdataset.config'))['pool'] == await middleware.call('boot.pool_name'):
        await middleware.call('systemdataset.setup')


async def pool_post_import(middleware, pool):
    """
    On pool import we may need to reconfigure system dataset.
    """
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
