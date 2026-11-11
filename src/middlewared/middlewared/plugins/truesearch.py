from __future__ import annotations

import asyncio
import base64
import contextlib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import errno
import os
import stat
from typing import TYPE_CHECKING, Any, AsyncGenerator, Literal

from truenas_pylicensed.features import LicenseFeature
from truesearch_client import Busy, Client, Identity, NoIndex, OpenRequest, Refused, TruesearchError
from truesearch_client import CallError as BoundError
from truesearch_client.config import TARGETS_DIR, TargetRow, read_config, target_id
from truesearch_client.control import (
    INDEXER_CONTROL,
    RELEASE_TIMEOUT,
    IndexerStatus,
    IndexerTarget,
    UnindexedTarget,
    devices_of,
    indexer_status,
    served_ids,
    wait_released,
)
from truesearch_client.control import request as control_request

from middlewared.api import api_method
from middlewared.api.current import (
    TruesearchDatasetStatus,
    TruesearchEntry,
    TruesearchEntryType,
    TruesearchQuery,
    TruesearchQueryArgs,
    TruesearchQueryResult,
    TruesearchState,
    TruesearchStatusArgs,
    TruesearchStatusData,
    TruesearchStatusResult,
    UserGetUserObj,
    ZFSResourceQuery,
)
from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.plugins.service.services.truesearch import alive as units_alive
from middlewared.plugins.smb_.constants import SMBShareField as share_field
from middlewared.plugins.smb_.utils import is_time_machine_share
from middlewared.service import CallError, Service, ValidationError, private
from middlewared.utils.path import FSLocation, path_location
from middlewared.utils.smb import SearchProtocol, SMBSharePurpose
from middlewared.utils.truesearch_filters import spotlight_query
from middlewared.utils.zfs import query_imported_fast_impl

STATUS_TIMEOUT = 10  # seconds
# The schema name in the validation errors of truesearch.query.
_SCHEMA = 'truesearch_query'

if TYPE_CHECKING:
    from middlewared.main import Middleware


@dataclass(frozen=True, slots=True)
class IndexedDataset:
    """A dataset that the daemons index now: its name, the indexed directory, and its mountpoint."""
    dataset: str
    root: str
    mountpoint: str


@dataclass(frozen=True, slots=True)
class DatasetInfo:
    name: str
    guid: str | None


class TruesearchService(Service):
    class Config:
        namespace = 'truesearch'
        cli_namespace = 'system.truesearch'

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        # Paths mounted since the last check, see schedule_mount_check()
        self.mounted_paths: set[str] = set()
        self.mount_check_timer: asyncio.TimerHandle | None = None
        # The mountpoints that are about to be destroyed. remove_mountpoint() adds them. Their rows are disabled.
        self.releasing: list[str] = []
        self.configure_lock = asyncio.Lock()
        # The datasets that the daemons index now, with the generation that they were read in. _indexed_datasets()
        # fills this when a query needs it. A change of the configuration file or a mount starts a new generation.
        self._indexed: tuple[int, list[IndexedDataset]] | None = None
        self._generation = 0

    @private
    async def unavailable_reasons(self) -> list[str]:
        """
        Returns a list of reasons why the truesearch service cannot be used.
        """
        reasons = []

        # The boot pool has no index dataset, because it cannot hold an encrypted dataset.
        if await self.middleware.call('systemdataset.is_boot_pool'):
            reasons.append('The system dataset must not reside on the boot pool.')
        # setup_datasets leaves the index dataset unmounted when it cannot use the dataset.
        elif not await self.middleware.run_in_thread(_index_dataset_mounted):
            reasons.append('The TrueSearch index dataset is not mounted. The middleware log gives the reason.')

        entitlement = await self.call2(self.s.truenas.entitlements.check, LicenseFeature.TRUESEARCH)
        if not entitlement.entitled:
            reasons.append(entitlement.message)

        return reasons

    @private
    async def available(self) -> bool:
        """
        Whether the truesearch service can be used.
        """
        return not bool(await self.call2(self.s.truesearch.unavailable_reasons))

    @private
    async def enabled(self) -> bool:
        """
        Whether the truesearch service should run. It must be available, and a share must name a directory in a
        dataset.
        """
        if not await self.available() or not (directories := await self.raw_directories()):
            return False

        datasets = await self.datasets(_pools(directories))
        return any(self._dataset_of(datasets, directory) is not None for directory in directories)

    @private
    async def datasets(self, pools: set[str]) -> dict[str, DatasetInfo]:
        """
        The filesystems of `pools`, by mountpoint.
        """
        result = {}
        for dataset in await self.call2(self.s.zfs.resource.list_impl, ZFSResourceQuery(
            paths=pools,
            properties=['mountpoint', 'guid'],
            get_children=True,
        )):
            if dataset['type'] != 'FILESYSTEM':
                continue

            properties = dataset['properties']
            mountpoint = properties['mountpoint']['value']
            if mountpoint and mountpoint not in ('legacy', 'none'):
                guid = (properties.get('guid') or {}).get('value')
                result[mountpoint] = DatasetInfo(name=dataset.get('name', ''), guid=str(guid) if guid else None)

        return result

    def _processed_directories_for_directory(self, mountpoints: dict[str, Any], directory: str) -> set[str]:
        """
        The directory, and the mountpoint of each dataset beneath it. Each dataset has an index of its own. A directory
        that is in no dataset gives nothing.
        """
        if self._dataset_of(mountpoints, directory) is None:
            return set()

        return {directory} | {mountpoint for mountpoint in mountpoints if beneath(mountpoint, directory)}

    @staticmethod
    def _dataset_of(mountpoints: set[str] | dict[str, Any], path: str) -> str | None:
        """
        The mountpoint of the dataset that holds `path`.
        """
        while True:
            if path in mountpoints:
                return path
            if path in ('/', '/mnt'):
                return None
            path = os.path.dirname(path)

    @private
    async def targets(self) -> list[TargetRow]:
        """
        The index targets of truesearchd. A dataset has one row if it holds an indexed directory or is mounted beneath
        one. The root of the row is the directory that those directories share. truesearchd serves one index target
        on a filesystem, and every share beneath its root. A Time Machine share is not indexed. A Time Machine share
        beneath the root is excluded, and its own dataset gets no row.

        Some rows are disabled and keep their indexes. These are the datasets whose shares are disabled, whose share
        service does not run, or whose pool is not imported. Also disabled are the datasets that are locked, about to
        be locked or about to be destroyed. A row leaves the file when no share names a directory in it. `configure`
        then drops its index.
        """
        indexed = await self.raw_directories()
        # The directories of all shares. They include the indexed directories.
        shared = await self.raw_directories(enabled_only=False)
        if not shared:
            return []

        timemachine = await self.timemachine_directories()
        rows = self._rows(await self.datasets(_pools(shared | timemachine)), indexed, shared, timemachine)
        # A locked dataset, and a dataset that a lock is about to unmount, keep a disabled row. A share in such a
        # dataset reads as locked already, but a child dataset beneath a share does not.
        rows = [
            replace(row, enabled=False)
            if row.enabled and await self.call2(self.s.zfs.resource.path_is_locked, row.dataset) else row
            for row in rows
        ]
        if old := await self.middleware.run_in_thread(read_config):
            imported = await self.middleware.run_in_thread(query_imported_fast_impl)
            rows += carried_rows(old, rows, {pool['name'] for pool in imported.values()}, shared)

        return sorted(rows, key=lambda row: row.id)

    def _rows(
        self, datasets: dict[str, DatasetInfo], indexed: set[str], shared: set[str], timemachine: set[str],
    ) -> list[TargetRow]:
        """
        The rows of the datasets of `indexed`, then a disabled row for each other dataset of `shared`. A row at or
        beneath a mountpoint about to be destroyed is disabled.
        """
        rows = [
            replace(row, enabled=False) if any(beneath(row.root, path) for path in self.releasing) else row
            for row in self._dataset_rows(datasets, indexed, timemachine)
        ]
        ids = {row.id for row in rows}
        rows += [
            replace(row, enabled=False)
            for row in self._dataset_rows(datasets, shared, timemachine)
            if row.id not in ids
        ]
        return rows

    def _dataset_rows(
        self, datasets: dict[str, DatasetInfo], raw: set[str], timemachine: set[str],
    ) -> list[TargetRow]:
        directories = set()
        for directory in raw:
            directories |= self._processed_directories_for_directory(datasets, directory)

        # The dataset of a Time Machine share, and every dataset beneath it, is not indexed.
        directories = {
            directory for directory in directories if not any(beneath(directory, path) for path in timemachine)
        }

        by_dataset: dict[str, list[str]] = {}
        for directory in directories:
            if (mountpoint := self._dataset_of(datasets, directory)) is not None:
                by_dataset.setdefault(mountpoint, []).append(directory)

        rows = []
        for mountpoint, members in by_dataset.items():
            root = os.path.commonpath(members)
            dataset = datasets[mountpoint]
            exclude = tuple(sorted(
                os.path.relpath(path, root)
                for path in timemachine
                if path != root
                and beneath(path, root)
                and self._dataset_of(datasets, path) == mountpoint
            ))
            rows.append(TargetRow(
                id=target_id(dataset.name, dataset.guid), dataset=dataset.name, root=root, exclude=exclude,
            ))

        return rows

    @private
    async def raw_directories(self, enabled_only: bool = True) -> set[str]:
        """
        The directories of the shares to index. With `enabled_only` false, also the directories of the shares that are
        disabled or whose service does not run.
        """
        return await self.smb_directories(enabled_only) | await self.webshare_directories(enabled_only)

    @private
    async def smb_directories(self, enabled_only: bool = True) -> set[str]:
        """
        What Samba shares directories should it index.
        """
        smb_config = await self.middleware.call('smb.config')
        if SearchProtocol.SPOTLIGHT not in smb_config['search_protocols']:
            return set()

        if enabled_only and not await self.call2(self.s.service.started_or_enabled, 'cifs'):
            return set()

        if enabled_only:
            shares = await self.middleware.call(
                'sharing.smb.query', [[share_field.ENABLED, '=', True]], {'force_sql_filters': True},
            )
        else:
            # Middleware does not check the lock of a share that is not indexed. Its dataset gets a disabled row in
            # both cases.
            shares = await self.middleware.call(
                'sharing.smb.query', [], {'force_sql_filters': True, 'extra': {'retrieve_locked_info': False}},
            )

        return {
            share[share_field.PATH]
            for share in shares
            if (
                (not enabled_only or share[share_field.LOCKED] is False)
                and path_location(share[share_field.PATH]) is FSLocation.LOCAL
                and not is_time_machine_share(share)
                and not _is_home_share(share)
            )
        }

    @private
    async def timemachine_directories(self) -> set[str]:
        """
        The directories of Time Machine shares. They are not indexed. A disabled share keeps its backups, so its
        directory is not indexed either.
        """
        shares = await self.middleware.call(
            'sharing.smb.query', [], {'force_sql_filters': True, 'extra': {'retrieve_locked_info': False}},
        )

        return {
            share[share_field.PATH]
            for share in shares
            if path_location(share[share_field.PATH]) is FSLocation.LOCAL and is_time_machine_share(share)
        }

    @private
    async def webshare_directories(self, enabled_only: bool = True) -> set[str]:
        """
        What WebShare shares directories should it index.
        """
        webshare_config = await self.call2(self.s.webshare.config)
        if not webshare_config.search:
            return set()

        # TODO: The home base share is not indexed. The home datasets of the users need a design of their own.
        if not enabled_only:
            shares = await self.call2(self.s.sharing.webshare.query, [])
            assert isinstance(shares, list)
            return {share.path for share in shares if not share.is_home_base}

        if not await self.call2(self.s.service.started_or_enabled, 'webshare'):
            return set()

        shares = await self.call2(self.s.sharing.webshare.query, [['enabled', '=', True]])
        assert isinstance(shares, list)

        return {share.path for share in shares if share.locked is False and not share.is_home_base}

    MOUNT_CHECK_DELAY = 1  # seconds

    @private
    async def schedule_mount_check(self, mountpoint: str) -> None:
        """
        Check newly mounted paths against the indexed directories 1 second after the last mount. A pool import
        mounts its datasets in a burst, and looking up the indexed directories queries service state, so doing it
        for every mount is expensive.
        """
        # A mount can change the mountpoint of an indexed dataset.
        self._generation += 1
        self.mounted_paths.add(mountpoint)
        if self.mount_check_timer is not None:
            self.mount_check_timer.cancel()

        self.mount_check_timer = asyncio.get_running_loop().call_later(
            self.MOUNT_CHECK_DELAY,
            lambda: self.middleware.create_task(self.check_mounted_paths())
        )

    @private
    async def check_mounted_paths(self) -> None:
        mounted, self.mounted_paths = self.mounted_paths, set()
        # A mount that arrives just before an earlier check starts is taken by
        # that check, and leaves nothing for the timer it scheduled.
        if not mounted:
            return

        try:
            directories = await self.raw_directories()
        except Exception:
            self.logger.exception(
                'TrueSearch: failed to check %d mounted paths against indexed directories', len(mounted)
            )
            return

        for mountpoint in mounted:
            for directory in directories:
                paths = {directory, mountpoint}
                # If the mounted path is a child of the share, or the share is a child of the mounted path,
                # reconfigure TS
                if os.path.commonpath(list(paths)) in paths:
                    self.logger.info(
                        f"Mounted path {mountpoint!r} intersects with indexed directory {directory}. "
                        "Reconfiguring TrueSearch."
                    )
                    await self.configure()
                    return

    @private
    async def configure(self) -> None:
        """
        Start, reload or stop the service, as `enabled` decides. A reload returns when both daemons release the
        datasets of the rows that it disabled or removed. The indexer removes the index of a row that left the file.
        """
        async with self.configure_lock:
            enabled = await self.enabled()
            running = await self.call2(self.s.service.started, 'truesearch')
            before = await self.middleware.run_in_thread(read_config)

            verb: Literal['START', 'STOP', 'RESTART', 'RELOAD']
            try:
                if enabled and running:
                    verb = 'RELOAD'
                # The service is stopped when one daemon is down. The daemon that runs reads the file only when it
                # starts, so it restarts.
                elif enabled:
                    verb = 'RESTART' if await self.alive() else 'START'
                elif await self.alive():
                    verb = 'STOP'
                else:
                    return

                done = await (await self.call2(self.s.service.control, verb, 'truesearch')).wait(raise_error=True)
            finally:
                # The configuration file can have other rows now.
                self._generation += 1

            if not done:
                self.logger.error('TrueSearch: the service failed to %s.', verb.lower())
            if verb == 'STOP':
                return

            after = await self.middleware.run_in_thread(read_config)
            if before is None or after is None:
                return

            # A daemon that did not reload still holds the datasets.
            if running and done:
                await self.middleware.run_in_thread(self._wait_released, before, after)
            # The rows that left the file are dropped even when the service failed. It wrote the file first, so the
            # next configure() does not see them leave.
            if gone := {row.id for row in before} - {row.id for row in after}:
                await self.middleware.run_in_thread(self._drop, sorted(gone))

    def _wait_released(self, before: list[TargetRow], after: list[TargetRow]) -> None:
        held = {row.id: row.root for row in after if row.enabled}
        released = [row.root for row in before if row.enabled and row.root and row.id not in held]
        # Do not wait for a dataset that a row still holds.
        devices = devices_of(released) - devices_of(held.values())
        if devices and not wait_released(devices):
            self.logger.warning(
                'TrueSearch: a daemon still holds a dataset of %s %d seconds after the reload.',
                released, RELEASE_TIMEOUT,
            )

    def _drop(self, ids: list[str]) -> None:
        for id_ in ids:
            try:
                answer = control_request(INDEXER_CONTROL, f'drop {id_}')
            except OSError as e:
                self.logger.warning('TrueSearch: index target %s was not dropped: %s', id_, e, exc_info=True)
            else:
                self.logger.info('TrueSearch: dropping index target %s: %s', id_, answer)

    @private
    async def alive(self) -> bool:
        """
        Whether truesearchd or truesearch-indexer runs. The service is started only when both run. A step that needs
        the daemons to let go of a dataset asks this, because one daemon alone still holds it.
        """
        return await units_alive()

    @private
    @contextlib.asynccontextmanager
    async def remove_mountpoint(self, mountpoint: str | None) -> AsyncGenerator[None, None]:
        """
        Release the index targets at and beneath `mountpoint` before it is destroyed, so that it can be unmounted.
        Both daemons reload with those rows disabled and continue to serve the other datasets. After the destroy, the
        rows of the datasets that are gone leave the file, and `configure` drops their indexes.
        """
        held = []
        if mountpoint is not None and await self.alive():
            rows = await self.middleware.run_in_thread(read_config) or []
            held = [row.root for row in rows if row.enabled and beneath(row.root, mountpoint)]

        if not held:
            yield
            return

        assert mountpoint is not None
        self.logger.info('TrueSearch: releasing %s before %r is destroyed.', held, mountpoint)
        self.releasing.append(mountpoint)
        try:
            await self.configure()
            yield
        finally:
            self.releasing.remove(mountpoint)
            try:
                await self.configure()
            except Exception:
                self.logger.error('TrueSearch: failed to configure after %r was destroyed.', mountpoint, exc_info=True)

    @api_method(
        TruesearchQueryArgs, TruesearchQueryResult, roles=['READONLY_ADMIN'], check_annotations=True,
    )
    def query(self, data: TruesearchQuery) -> list[TruesearchEntry]:
        """
        Search the TrueSearch index for files and directories in ``path`` and its subdirectories.

        TrueSearch uses the index that answers macOS Spotlight searches through SMB. Middleware converts the filters
        into a Spotlight query. Thus, a query gets the same results as a Spotlight search from a Mac.
        """
        try:
            query = spotlight_query(data.query_filters)
        except ValueError as e:
            raise ValidationError(f'{_SCHEMA}.query-filters', str(e))

        searches = self._searches(data.path, data.recursive)
        uid, gid = 0, 0
        groups: list[int] = []
        if data.username is not None:
            uid, gid, groups, searches = self._user_identity(data.username, searches)

        hits: list[tuple[str, Any]] = []
        try:
            with Client() as client:
                for search_dir, mountpoint, dataset in searches:
                    share = os.path.relpath(search_dir, mountpoint)
                    request = OpenRequest(
                        dataset=dataset,
                        share='' if share == '.' else share,
                        query=query,
                        who=Identity(uid, gid, tuple(groups)),
                        max_results=data.query_options.limit,
                    )
                    try:
                        found = client.search(request)
                    except NoIndex:
                        if not data.recursive:
                            raise CallError(f'{search_dir!r} is not indexed.', errno.ENOENT)

                        # TrueSearch does not serve this dataset now, for example during its first build.
                        continue

                    hits += [
                        (os.path.join(search_dir, hit.path) if hit.path else search_dir, hit.st) for hit in found.hits
                    ]
        except Busy:
            raise CallError('TrueSearch is busy. Try again later.', errno.EBUSY)
        except Refused as e:
            raise CallError(f'TrueSearch refused the search: {e.detail}', errno.EINVAL)
        except BoundError as e:
            # The query is too long, or the user is in too many groups. The client sent nothing.
            raise CallError(f'The search is past a limit of TrueSearch: {e}', errno.EINVAL)
        except (OSError, TruesearchError) as e:
            raise CallError(f'TrueSearch is not available: {e}', errno.ENOTCONN)

        if len(searches) > 1:
            # Each dataset returns its newest entries first. The merge keeps that order across the datasets. Only the
            # hits that are kept become entries.
            hits.sort(key=_created, reverse=True)

        return [_entry(path, st) for path, st in hits[:data.query_options.limit]]

    def _searches(self, path: str, recursive: bool) -> list[tuple[str, str, str]]:
        """
        The searches of a query. Each search is a directory, the mountpoint of its dataset, and the name of the
        dataset. The first search is in the dataset that contains `path`. If `path` is above the indexed directory
        of that dataset, the search covers all of the indexed directory. With `recursive`, there is also one search
        for each indexed dataset that is mounted beneath `path`.
        """
        parts = path.strip('/').split('/')
        # `/mnt/` is `/mnt` once it is normalized, and a search of `/mnt` would cover every pool.
        if not path.startswith('/mnt/') or len(parts) < 2 or any(part in ('', '.', '..') for part in parts):
            raise ValidationError(
                f'{_SCHEMA}.path', 'Must be an absolute path beneath /mnt with no "." or ".." component.',
            )

        path = '/' + '/'.join(parts)
        indexed = self._indexed_datasets()
        # The dataset that contains `path` is the indexed dataset with the deepest mountpoint above `path`.
        holder = max(
            (item for item in indexed if beneath(path, item.mountpoint)),
            key=lambda item: len(item.mountpoint),
            default=None,
        )
        searches = []
        if holder is not None:
            if beneath(path, holder.root):
                searches.append((path, holder.mountpoint, holder.dataset))
            elif beneath(holder.root, path):
                searches.append((holder.root, holder.mountpoint, holder.dataset))

        if recursive:
            searches += sorted(
                (item.root, item.mountpoint, item.dataset)
                for item in indexed
                if item is not holder and beneath(item.mountpoint, path)
            )

        if searches:
            return searches
        if holder is not None:
            raise CallError(
                f'{path!r} is not indexed. The index of {holder.dataset!r} is {holder.root!r}.', errno.ENOENT,
            )

        raise CallError(f'{path!r} is not in a dataset that TrueSearch indexes.', errno.ENOENT)

    def _indexed_datasets(self) -> list[IndexedDataset]:
        """
        The datasets that the daemons index now. They are the enabled rows of the configuration file, with their
        mountpoints. The list stays until `configure` writes the file again or a dataset is mounted. Thus, a query of
        a path that is not indexed fails at once.
        """
        generation = self._generation
        if (cached := self._indexed) is not None and cached[0] == generation:
            return cached[1]

        rows = [row for row in read_config() or [] if row.enabled]
        mountpoints = {}
        if rows:
            for found in self.call_sync2(self.s.zfs.resource.list_impl, ZFSResourceQuery(
                paths=[row.dataset for row in rows], properties=['mountpoint'],
            )):
                mountpoint = found['properties']['mountpoint']['value']
                if found['type'] == 'FILESYSTEM' and mountpoint and mountpoint not in ('legacy', 'none'):
                    mountpoints[found['name']] = mountpoint

        indexed = [
            IndexedDataset(dataset=row.dataset, root=row.root, mountpoint=mountpoints[row.dataset])
            for row in rows
            if row.dataset in mountpoints
        ]
        # A configure or a mount during this read starts a new generation. Then the list serves this query only.
        self._indexed = (generation, indexed)
        return indexed

    def _user_identity(
        self, username: str, searches: list[tuple[str, str, str]],
    ) -> tuple[int, int, list[int], list[tuple[str, str, str]]]:
        """
        The IDs and groups of the user, and the searches that the user can reach. truesearchd checks access from the
        searched directory down. Middleware checks the directories above it. A recursive query skips a dataset that
        the user cannot reach.
        """
        try:
            user = self.call_sync2(self.s.user.get_user_obj, UserGetUserObj(username=username, get_groups=True))
        except KeyError:
            raise ValidationError(f'{_SCHEMA}.username', f'{username!r}: no such user.')

        # One lookup of the user serves all searches. A directory that is gone since the configuration file was
        # written is not refused here. truesearchd does not serve it, and a recursive query skips it.
        details = user.model_dump()
        reachable = [
            search for search in searches
            if not self.middleware.call_sync(
                'filesystem.can_access_as_cred_errors', details, search[0], ['READ', 'EXECUTE'], False, True,
            )
        ]
        if not reachable:
            raise CallError(f'{username!r} cannot reach {searches[0][0]!r}.', errno.EACCES)

        return user.pw_uid, user.pw_gid, list(user.grouplist or []), reachable

    @api_method(TruesearchStatusArgs, TruesearchStatusResult, roles=['SERVICE_READ'], check_annotations=True)
    def status(self) -> TruesearchStatusData:
        """
        Get the status of the index of each dataset that TrueSearch indexes.

        For each dataset, the status gives the state of the index, the number of entries in it, and the time of the
        last update. It also tells whether searches use the index.
        """
        # The daemons index and serve the enabled rows of the configuration file.
        rows = [row for row in read_config() or [] if row.enabled]
        try:
            indexer = indexer_status(STATUS_TIMEOUT)
        except (OSError, ValueError):
            indexer = None
        try:
            served = served_ids(STATUS_TIMEOUT)
        except (OSError, ValueError):
            served = set()

        return TruesearchStatusData(
            running=indexer is not None,
            index_bytes=None if indexer is None else indexer.index_bytes,
            free_bytes=None if indexer is None else indexer.free_bytes,
            space_low=None if indexer is None else indexer.space_low,
            datasets=[_dataset_status(row, indexer, served) for row in rows],
        )


def _when(seconds: int) -> datetime | None:
    return datetime.fromtimestamp(seconds, tz=timezone.utc) if seconds else None


def _dataset_status(row: TargetRow, indexer: IndexerStatus | None, served: set[str]) -> TruesearchDatasetStatus:
    target = None if indexer is None else indexer.targets.get(row.id)
    state: TruesearchState
    reason: str | None = None
    match target:
        case None:
            state = 'STOPPED' if indexer is None else 'INDEXING'
        case UnindexedTarget():
            state = 'UNAVAILABLE'
            reason = target.why
        case IndexerTarget(activity='idle'):
            state = 'READY'
        case IndexerTarget(activity='waiting for its root'):
            state = 'UNAVAILABLE'
            reason = f'The dataset is not mounted at {row.root!r}.'
        case _:
            state = 'INDEXING'

    # The indexer gives counts only for the index targets that it runs.
    counted = target if isinstance(target, IndexerTarget) else None
    return TruesearchDatasetStatus(
        dataset=row.dataset,
        path=row.root,
        state=state,
        reason=reason,
        served=row.id in served,
        entries=None if counted is None else counted.live,
        watching=None if counted is None else counted.watching,
        last_full_pass=None if counted is None else _when(counted.last_full),
        last_directory_pass=None if counted is None else _when(counted.last_dirs),
        index_size=None if counted is None else counted.size,
    )


def _is_home_share(share: dict[str, Any]) -> bool:
    """
    Whether an SMB share is a home share, or a share that makes a dataset for each user.
    """
    # TODO: Home shares are not indexed. The home datasets of the users need a design of their own.
    return (
        share[share_field.PURPOSE] == SMBSharePurpose.PRIVATE_DATASETS_SHARE
        or bool((share.get(share_field.OPTS) or {}).get(share_field.HOME))
    )


def _index_dataset_mounted() -> bool:
    return os.path.ismount(TARGETS_DIR)


def beneath(path: str, top: str) -> bool:
    """Whether `path` is `top` or a path beneath it."""
    return path == top or path.startswith(top.rstrip('/') + '/')


def carried_rows(
    old: list[TargetRow], rows: list[TargetRow], imported: set[str], directories: set[str],
) -> list[TargetRow]:
    """
    The rows of the file `old` that stay, disabled, because their pool is not imported. A row stays while a share
    directory of `directories` is in its root or above it. So an exported pool keeps its index until its shares are
    deleted. A row of an imported pool is not carried, because its dataset is gone.
    """
    ids = {row.id for row in rows}
    roots = {row.root for row in rows}
    return [
        replace(row, enabled=False, exclude=())
        for row in old
        if row.root
        and row.dataset
        and row.dataset.split('/')[0] not in imported
        and row.id not in ids
        and row.root not in roots
        and any(beneath(row.root, directory) or beneath(directory, row.root) for directory in directories)
    ]


def _pools(directories: set[str]) -> set[str]:
    """The pools of directories beneath /mnt."""
    return {directory.removeprefix('/mnt/').split('/')[0] for directory in directories}


def _created(hit: tuple[str, Any]) -> tuple[int, int]:
    """The sort key of a hit: the creation time in its stat, or zero for a hit without a stat."""
    st = hit[1]
    return (0, 0) if st is None else (st.btime_sec, st.btime_nsec)


def _hit_type(mode: int) -> TruesearchEntryType:
    if stat.S_ISDIR(mode):
        return 'DIRECTORY'
    if stat.S_ISREG(mode):
        return 'FILE'
    if stat.S_ISLNK(mode):
        return 'SYMLINK'
    return 'OTHER'


def _time(seconds: int, nanoseconds: int) -> datetime | None:
    """
    A time of a stat, to the microsecond. It is never rounded up into the next second. A time that `datetime` cannot
    hold, such as a year after 9999, is None.
    """
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(microsecond=nanoseconds // 1000)
    except (OverflowError, OSError, ValueError):
        return None


def _entry(path: str, st: Any) -> TruesearchEntry:
    if st is None:
        return TruesearchEntry(
            path=path, name=os.path.basename(path), type='OTHER', size=None, mode=None, uid=None, gid=None,
            mtime=None, btime=None, atime=None, inode=None, handle=None,
        )

    return TruesearchEntry(
        path=path,
        name=os.path.basename(path),
        type=_hit_type(st.mode),
        size=st.size,
        mode=st.mode,
        uid=st.uid,
        gid=st.gid,
        mtime=_time(st.mtime_sec, st.mtime_nsec),
        btime=_time(st.btime_sec, st.btime_nsec),
        atime=_time(st.atime_sec, st.atime_nsec),
        inode=st.ino,
        handle=base64.b64encode(st.handle).decode(),
    )


class TrueSearchFSAttachmentDelegate(FSAttachmentDelegate[TargetRow]):
    """
    The index targets on a pool or a dataset. A pool export disables the shares of the pool first. Then this delegate
    reloads TrueSearch with their rows disabled. So both daemons release the pool before the export checks for
    processes, and the pool keeps its indexes for the next import.
    """
    name = 'truesearch'
    title = 'TrueSearch Index'
    resource_name = 'dataset'
    # The share delegates run first, at priority 0. Then the rows of their datasets are disabled.
    priority = 1

    async def query(self, path: str, enabled: bool, options: dict[str, Any] | None = None) -> list[TargetRow]:
        """
        The rows both daemons hold at or beneath `path`. No disabled row is listed. TrueSearch follows the shares, and
        `pool.post_import` configures it after an import.
        """
        if not enabled or not await self.call2(self.s.truesearch.alive):
            return []

        exact = (options or {}).get('exact_match', False)
        rows = await self.middleware.run_in_thread(read_config) or []
        return [row for row in rows if row.enabled and (row.root == path if exact else beneath(row.root, path))]

    async def delete(self, attachments: list[TargetRow]) -> None:
        await self.call2(self.s.truesearch.configure)

    async def toggle(self, attachments: list[TargetRow], enabled: bool) -> None:
        await self.call2(self.s.truesearch.configure)

    async def stop(self, attachments: list[TargetRow]) -> None:
        await self.call2(self.s.truesearch.configure)

    async def start(self, attachments: list[TargetRow]) -> None:
        await self.call2(self.s.truesearch.configure)


async def post_license_update(middleware: Middleware, *args: tuple[Any], **kwargs: dict[str, Any]) -> None:
    await middleware.call2(middleware.services.truesearch.configure)


async def on_dataset_mounted(middleware: Middleware, data: dict[str, Any]) -> None:
    await middleware.call2(middleware.services.truesearch.schedule_mount_check, data['mountpoint'])


async def on_pool_post_import(middleware: Middleware, pool: dict[str, Any] | None) -> None:
    # The import enabled the shares that the export disabled. system.ready follows an import at boot.
    if pool is not None:
        await middleware.call2(middleware.services.truesearch.configure)


async def on_pool_post_export(middleware: Middleware, *args: Any, **kwargs: Any) -> None:
    # The rows of the pool stay in the file, disabled, as long as its shares exist. A daemon that the export stopped
    # starts again.
    await middleware.call2(middleware.services.truesearch.configure)


async def on_system_ready(middleware: Middleware, event_type: str, args: Any) -> None:
    if await middleware.call('failover.licensed'):
        return

    await middleware.call2(middleware.services.truesearch.configure)


async def setup(middleware: Middleware) -> None:
    middleware.register_hook("system.post_license_update", post_license_update, sync=False)
    middleware.register_hook("zfs.dataset.mounted", on_dataset_mounted)
    middleware.register_hook("pool.post_import", on_pool_post_import, sync=False)
    middleware.register_hook("pool.post_export", on_pool_post_export, sync=False)
    middleware.event_subscribe("system.ready", on_system_ready)
    await middleware.call2(
        middleware.services.zfs.resource.register_attachment_delegate, TrueSearchFSAttachmentDelegate(middleware),
    )
