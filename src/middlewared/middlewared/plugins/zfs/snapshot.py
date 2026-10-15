from __future__ import annotations

# Methods named after builtins shadow them within the class body, so annotations after such a method
# must qualify the type through `builtins` to refer to the type rather than the method.
import builtins
from typing import Any

from middlewared.api import Event, api_method
from middlewared.api.current import (
    ZFSResourceSnapshotCloneArgs,
    ZFSResourceSnapshotCloneArgsData,
    ZFSResourceSnapshotCloneResult,
    ZFSResourceSnapshotCountArgs,
    ZFSResourceSnapshotCountQuery,
    ZFSResourceSnapshotCountResult,
    ZFSResourceSnapshotCreateArgs,
    ZFSResourceSnapshotCreateArgsData,
    ZFSResourceSnapshotCreateResult,
    ZFSResourceSnapshotDestroyArgs,
    ZFSResourceSnapshotDestroyArgsData,
    ZFSResourceSnapshotDestroyResult,
    ZFSResourceSnapshotEntry,
    ZFSResourceSnapshotHoldArgs,
    ZFSResourceSnapshotHoldArgsData,
    ZFSResourceSnapshotHoldResult,
    ZFSResourceSnapshotHoldsArgs,
    ZFSResourceSnapshotHoldsQuery,
    ZFSResourceSnapshotHoldsResult,
    ZFSResourceSnapshotListAddedEvent,
    ZFSResourceSnapshotListArgs,
    ZFSResourceSnapshotListChangedEvent,
    ZFSResourceSnapshotListRemovedEvent,
    ZFSResourceSnapshotListResult,
    ZFSResourceSnapshotQuery,
    ZFSResourceSnapshotQueryArgs,
    ZFSResourceSnapshotQueryResult,
    ZFSResourceSnapshotReleaseArgs,
    ZFSResourceSnapshotReleaseArgsData,
    ZFSResourceSnapshotReleaseResult,
    ZFSResourceSnapshotRenameArgs,
    ZFSResourceSnapshotRenameArgsData,
    ZFSResourceSnapshotRenameResult,
    ZFSResourceSnapshotRollbackArgs,
    ZFSResourceSnapshotRollbackArgsData,
    ZFSResourceSnapshotRollbackResult,
)
from middlewared.service import Service, private
from middlewared.service.decorators import pass_thread_local_storage

from . import snapshot_ops as _ops
from .snapshot_count_impl import count_snapshots_impl

__all__ = ("ZFSResourceSnapshotService",)


def audit_target(target: object, data: dict[str, Any], *flags: str) -> str:
    if present := [flag for flag in flags if data.get(flag)]:
        return f"{target} ({', '.join(present)})"
    return f"{target}"


class ZFSResourceSnapshotService(Service):
    class Config:
        namespace = "zfs.resource.snapshot"
        cli_private = True
        entry = ZFSResourceSnapshotEntry
        events = [
            Event(
                name="zfs.resource.snapshot.list",
                description=(
                    "Snapshots created, renamed, held or released through this API, and snapshots destroyed by any "
                    "means. ADDED is sent for a snapshot created or renamed through this API. CHANGED carries the "
                    "holds after a hold or release through this API. REMOVED is sent for the old name of a renamed "
                    "snapshot and for every destroyed snapshot, including destroys by the zfs command, retention and "
                    "rollback. A REMOVED for a destroy comes from ZFS history events: it arrives after the destroy "
                    "returns, may follow an ADDED for a new snapshot of the same name, and can be lost when events "
                    "are dropped under load. Snapshots created outside this API, such as by periodic snapshot tasks, "
                    "replication or the zfs command, emit nothing, and neither do the descendants' snapshots in a "
                    "recursive snapshot rename, renaming or promoting a dataset, or exporting or destroying a pool."
                ),
                roles=["SNAPSHOT_READ"],
                models={
                    "ADDED": ZFSResourceSnapshotListAddedEvent,
                    "CHANGED": ZFSResourceSnapshotListChangedEvent,
                    "REMOVED": ZFSResourceSnapshotListRemovedEvent,
                },
            )
        ]

    @private
    @pass_thread_local_storage
    def list_impl(self, tls: Any, data: ZFSResourceSnapshotQuery) -> builtins.list[dict[str, Any]]:
        return _ops.list_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotListArgs,
        ZFSResourceSnapshotListResult,
        roles=["SNAPSHOT_READ"],
        check_annotations=True,
    )
    def list(self, data: ZFSResourceSnapshotQuery) -> builtins.list[ZFSResourceSnapshotEntry]:
        """
        List ZFS snapshots and, on request, their properties, user properties and holds.

        ``paths`` takes dataset paths, which select the snapshots of that dataset, and snapshot paths, which
        select that one snapshot. A path that does not exist is skipped. Without ``paths`` the snapshots of
        every pool's root filesystem are listed; set ``recursive`` to include the snapshots of descendants.
        Snapshots of internal datasets are left out unless one is named in ``paths``. Snapshots have no
        default properties, so request the ones needed in ``properties``.

        A validation error is raised when ``recursive`` is set and one dataset path lies below another
        (``EINVAL``).

        Examples:

        List the snapshots of every pool's root filesystem:

        .. code:: json

            {}

        List every snapshot:

        .. code:: json

            {"recursive": true}

        List the snapshots of a dataset:

        .. code:: json

            {"paths": ["tank/data"]}

        Get one snapshot with its holds:

        .. code:: json

            {"paths": ["tank/data@backup"], "get_holds": true}

        List the snapshots of a dataset and its descendants with selected properties:

        .. code:: json

            {"paths": ["tank"], "recursive": true, "properties": ["used", "referenced", "creation"]}
        """
        return _ops.list_snapshots(self.context, data)

    @api_method(
        ZFSResourceSnapshotQueryArgs,
        ZFSResourceSnapshotQueryResult,
        roles=["SNAPSHOT_READ"],
        check_annotations=True,
        removed_in="v28",
    )
    def query(self, data: ZFSResourceSnapshotQuery) -> builtins.list[ZFSResourceSnapshotEntry]:
        """
        Retrieve information about ZFS snapshots, including their properties and user properties.
        """
        return _ops.list_snapshots(self.context, data)

    @private
    def exists(self, snap_name: str) -> bool:
        return _ops.exists(self.context, snap_name)

    @private
    @pass_thread_local_storage
    def count_impl(self, tls: Any, data: ZFSResourceSnapshotCountQuery) -> dict[str, int]:
        return count_snapshots_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotCountArgs,
        ZFSResourceSnapshotCountResult,
        roles=["SNAPSHOT_READ"],
        check_annotations=True,
    )
    def count(self, data: ZFSResourceSnapshotCountQuery) -> dict[str, int]:
        """
        Count ZFS snapshots per dataset.

        This method provides a fast way to count snapshots without retrieving full snapshot
        information. Useful for UI displays and quota checks.

        A snapshot path counts that snapshot toward its dataset. A path that does not exist is skipped.

        Examples:

        Count snapshots for root filesystems only:

        .. code:: json

            {}

        Count all snapshots recursively:

        .. code:: json

            {"recursive": true}

        Count snapshots for a specific dataset:

        .. code:: json

            {"paths": ["tank/data"]}

        Count snapshots for a dataset and all of its children:

        .. code:: json

            {"paths": ["tank"], "recursive": true}
        """
        return _ops.count(self.context, data)

    @private
    @pass_thread_local_storage
    def destroy_impl(self, tls: Any, data: ZFSResourceSnapshotDestroyArgsData) -> None:
        _ops.destroy_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotDestroyArgs,
        ZFSResourceSnapshotDestroyResult,
        roles=["SNAPSHOT_DELETE"],
        audit="ZFS snapshot destroy",
        audit_extended=lambda data: audit_target(data.get("path"), data, "recursive", "defer", "all_snapshots"),
        check_annotations=True,
    )
    def destroy(self, data: ZFSResourceSnapshotDestroyArgsData) -> None:
        """
        Destroy ZFS snapshots.

        A validation error is raised when:

        - ``path`` is not a snapshot path, or with ``all_snapshots`` is not a dataset path (``EINVAL``)
        - ``path`` does not exist (``ENOENT``)
        - it has dependent clones and ``defer`` is ``false`` (``EBUSY``)
        - it has active holds (``EBUSY``)
        - ``path`` is a protected path (``EACCES``)
        - the kernel refuses the destroy, with the errno it reported

        Examples:

        Destroy a single snapshot:

        .. code:: json

            {"path": "tank/data@backup"}

        Destroy matching snapshots in child datasets:

        .. code:: json

            {"path": "tank@backup", "recursive": true}

        Defer destruction if the snapshot is in use:

        .. code:: json

            {"path": "tank/data@snap", "defer": true}

        Destroy all snapshots of a dataset:

        .. code:: json

            {"path": "tank/data", "all_snapshots": true}

        Destroy all snapshots of a dataset and its children:

        .. code:: json

            {"path": "tank", "all_snapshots": true, "recursive": true}
        """
        _ops.destroy(self.context, data)

    @private
    @pass_thread_local_storage
    def rename_impl(self, tls: Any, data: ZFSResourceSnapshotRenameArgsData) -> None:
        return _ops.rename_impl(self.context, tls, data)

    @api_method(
        ZFSResourceSnapshotRenameArgs,
        ZFSResourceSnapshotRenameResult,
        roles=["SNAPSHOT_WRITE"],
        audit="ZFS snapshot rename from",
        audit_extended=lambda data: audit_target(
            f"{data.get('current_name')!r} to {data.get('new_name')!r}", data, "recursive"
        ),
        check_annotations=True,
    )
    def rename(self, data: ZFSResourceSnapshotRenameArgsData) -> None:
        """
        Rename a ZFS snapshot. The new name must stay on the same dataset.

        .. warning::

            No check is made whether the snapshot is in use. Replication, snapshot tasks and anything else
            that finds snapshots by name may break when one is renamed. Proceed only if you are certain the
            snapshot is not in use.

        A validation error is raised when:

        - ``force`` is not set (``EINVAL``)
        - ``current_name`` or ``new_name`` is not a snapshot path, or ``new_name`` is on a different dataset
          (``EINVAL``)
        - the snapshot does not exist (``ENOENT``)
        - ``new_name`` already exists (``EEXIST``)
        - either name is a protected path (``EACCES``)

        Examples:

        Rename a single snapshot:

        .. code:: json

            {"current_name": "tank/data@old", "new_name": "tank/data@new", "force": true}

        Rename matching snapshots in child datasets:

        .. code:: json

            {"current_name": "tank@old", "new_name": "tank@new", "recursive": true, "force": true}
        """
        _ops.rename(self.context, data)

    @private
    @pass_thread_local_storage
    def clone_impl(self, tls: Any, data: ZFSResourceSnapshotCloneArgsData) -> bool:
        return _ops.clone_impl(self.context, tls, data)

    @api_method(
        ZFSResourceSnapshotCloneArgs,
        ZFSResourceSnapshotCloneResult,
        roles=["SNAPSHOT_WRITE"],
        audit="ZFS snapshot clone",
        audit_extended=lambda data: f"{data.get('snapshot')!r} to {data.get('dataset')!r}",
        check_annotations=True,
    )
    def clone(self, data: ZFSResourceSnapshotCloneArgsData) -> None:
        """
        Clone a ZFS snapshot to create a new filesystem or volume, of the type the snapshot was taken of.

        A validation error is raised when:

        - ``snapshot`` is not a snapshot path or ``dataset`` is one (``EINVAL``)
        - a property does not apply to the type of the clone, or its value is refused (``EINVAL``)
        - a user property name or value is invalid (``EINVAL``)
        - the source snapshot does not exist (``ENOENT``)
        - ``dataset`` already exists (``EEXIST``)
        - either path is a protected path (``EACCES``)

        A filesystem clone that cannot be mounted is kept, and the error names it.

        Examples:

        Clone a snapshot to a new dataset:

        .. code:: json

            {"snapshot": "tank/data@backup", "dataset": "tank/data_clone"}

        Clone with properties:

        .. code:: json

            {
                "snapshot": "tank/data@backup",
                "dataset": "tank/data_clone",
                "properties": {"compression": "lz4", "quota": "10G"},
                "user_properties": {"org.truenas:origin": "backup"}
            }
        """
        _ops.clone(self.context, data)

    @private
    @pass_thread_local_storage
    def create_impl(self, tls: Any, data: ZFSResourceSnapshotCreateArgsData) -> dict[str, Any]:
        return _ops.create_impl(self.context, tls, data)

    @api_method(
        ZFSResourceSnapshotCreateArgs,
        ZFSResourceSnapshotCreateResult,
        roles=["SNAPSHOT_WRITE"],
        audit="ZFS snapshot create",
        audit_extended=lambda data: audit_target(f"{data.get('dataset')}@{data.get('name')}", data, "recursive"),
        check_annotations=True,
    )
    def create(self, data: ZFSResourceSnapshotCreateArgsData) -> ZFSResourceSnapshotEntry:
        """
        Create a ZFS snapshot, and with ``recursive`` the same-named snapshot of every descendant not listed in
        ``exclude``. All of them are created atomically.

        A validation error is raised when:

        - ``dataset`` or ``name`` contains ``@`` (``EINVAL``)
        - ``exclude`` leaves nothing to snapshot (``EINVAL``)
        - the dataset does not exist (``ENOENT``)
        - the snapshot already exists (``EEXIST``)
        - ``dataset`` is a protected path (``EACCES``)

        Examples:

        Create a single snapshot:

        .. code:: json

            {"dataset": "tank/data", "name": "backup"}

        Create snapshots recursively:

        .. code:: json

            {"dataset": "tank", "name": "backup", "recursive": true}

        Create with user properties:

        .. code:: json

            {"dataset": "tank/data", "name": "backup", "user_properties": {"com.company:backup_type": "daily"}}
        """
        return _ops.create(self.context, data)

    @private
    @pass_thread_local_storage
    def hold_impl(self, tls: Any, data: ZFSResourceSnapshotHoldArgsData) -> None:
        return _ops.hold_impl(self.context, tls, data)

    @api_method(
        ZFSResourceSnapshotHoldArgs,
        ZFSResourceSnapshotHoldResult,
        roles=["SNAPSHOT_WRITE"],
        audit="ZFS snapshot hold",
        audit_extended=lambda data: audit_target(data.get("path"), data, "recursive"),
        check_annotations=True,
    )
    def hold(self, data: ZFSResourceSnapshotHoldArgsData) -> None:
        """
        Create a hold on a ZFS snapshot.

        A hold prevents a snapshot from being destroyed. Multiple holds can be placed on a
        snapshot with different tags.

        A validation error is raised when:

        - ``path`` is not a snapshot path (``EINVAL``)
        - the hold tag is refused (``EINVAL``)
        - the snapshot does not exist (``ENOENT``)
        - ``path`` is a protected path (``EACCES``)

        Examples:

        Hold a snapshot:

        .. code:: json

            {"path": "tank/data@backup"}

        Hold with a custom tag:

        .. code:: json

            {"path": "tank/data@backup", "tag": "replication"}

        Hold matching snapshots in child datasets:

        .. code:: json

            {"path": "tank@backup", "recursive": true}
        """
        _ops.hold(self.context, data)

    @private
    @pass_thread_local_storage
    def holds_impl(self, tls: Any, path: str) -> tuple[str, ...]:
        return _ops.holds_impl(tls, path)

    @api_method(
        ZFSResourceSnapshotHoldsArgs,
        ZFSResourceSnapshotHoldsResult,
        roles=["SNAPSHOT_READ"],
        check_annotations=True,
        removed_in="v28",
    )
    def holds(self, data: ZFSResourceSnapshotHoldsQuery) -> builtins.list[str]:
        """
        Get holds on a ZFS snapshot.
        """
        return _ops.holds(self.context, data)

    @private
    @pass_thread_local_storage
    def release_impl(self, tls: Any, data: ZFSResourceSnapshotReleaseArgsData) -> None:
        return _ops.release_impl(self.context, tls, data)

    @api_method(
        ZFSResourceSnapshotReleaseArgs,
        ZFSResourceSnapshotReleaseResult,
        roles=["SNAPSHOT_WRITE"],
        audit="ZFS snapshot release",
        audit_extended=lambda data: audit_target(data.get("path"), data, "recursive"),
        check_annotations=True,
    )
    def release(self, data: ZFSResourceSnapshotReleaseArgsData) -> None:
        """
        Release hold(s) from a ZFS snapshot.

        A validation error is raised when:

        - ``path`` is not a snapshot path (``EINVAL``)
        - the snapshot does not exist (``ENOENT``)
        - ``path`` is a protected path (``EACCES``)

        Examples:

        Release a specific hold:

        .. code:: json

            {"path": "tank/data@backup", "tag": "replication"}

        Release all holds from a snapshot:

        .. code:: json

            {"path": "tank/data@backup"}

        Release a hold from matching snapshots in child datasets:

        .. code:: json

            {"path": "tank@backup", "tag": "backup", "recursive": true}
        """
        _ops.release(self.context, data)

    @private
    @pass_thread_local_storage
    def rollback_impl(self, tls: Any, data: ZFSResourceSnapshotRollbackArgsData) -> None:
        return _ops.rollback_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotRollbackArgs,
        ZFSResourceSnapshotRollbackResult,
        roles=["SNAPSHOT_WRITE"],
        audit="ZFS snapshot rollback",
        audit_extended=lambda data: audit_target(
            data.get("path"), data, "recursive", "recursive_clones", "recursive_rollback", "force"
        ),
        check_annotations=True,
    )
    def rollback(self, data: ZFSResourceSnapshotRollbackArgsData) -> None:
        """
        Rollback a ZFS dataset to a snapshot.

        .. warning::

            This is a destructive change. All data written since the target snapshot was
            taken will be discarded.

        A validation error is raised when:

        - the snapshot, or a child's snapshot, does not exist (errno ``ENOENT``)
        - ``path`` is not a snapshot path (errno ``EINVAL``)
        - snapshots more recent than ``path`` exist and neither ``recursive`` nor
          ``recursive_clones`` was passed (errno ``EINVAL``)
        - ``path`` is a protected path and the call did not come from the middleware itself
          (errno ``EACCES``)

        The call fails when:

        - a snapshot that has to be destroyed first has holds, or has clones and
          ``recursive_clones`` was not passed (errno ``EBUSY``); release a hold with
          :method:`zfs.resource.snapshot.release`
        - a destroy or the rollback itself fails, with the errno the kernel reported

        Examples:

        Roll back to a snapshot:

        .. code:: json

            {"path": "tank/data@backup"}

        Roll back, destroying more recent snapshots:

        .. code:: json

            {"path": "tank/data@backup", "recursive": true}

        Roll back all child datasets:

        .. code:: json

            {"path": "tank@backup", "recursive_rollback": true}
        """
        _ops.rollback(self.context, data)
