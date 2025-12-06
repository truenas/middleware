import errno

from middlewared.api import api_method
from middlewared.api.current import (
    ZFSResourceSnapshotEntry,
    ZFSResourceSnapshotCountArgs,
    ZFSResourceSnapshotCountResult,
    ZFSResourceSnapshotCloneArgs,
    ZFSResourceSnapshotCloneResult,
    ZFSResourceSnapshotCreateArgs,
    ZFSResourceSnapshotCreateResult,
    ZFSResourceSnapshotDestroyArgs,
    ZFSResourceSnapshotDestroyResult,
    ZFSResourceSnapshotHoldArgs,
    ZFSResourceSnapshotHoldResult,
    ZFSResourceSnapshotHoldsArgs,
    ZFSResourceSnapshotHoldsResult,
    ZFSResourceSnapshotQueryArgs,
    ZFSResourceSnapshotQueryResult,
    ZFSResourceSnapshotReleaseArgs,
    ZFSResourceSnapshotReleaseResult,
    ZFSResourceSnapshotRenameArgs,
    ZFSResourceSnapshotRenameResult,
    ZFSResourceSnapshotRollbackArgs,
    ZFSResourceSnapshotRollbackResult,
)
from middlewared.service import Service, private
from middlewared.service_exception import ValidationError
from middlewared.service.decorators import pass_thread_local_storage

from .destroy_impl import destroy_impl, DestroyArgs
from .exceptions import (
    ZFSPathAlreadyExistsException,
    ZFSPathHasClonesException,
    ZFSPathHasHoldsException,
    ZFSPathNotASnapshotException,
    ZFSPathNotFoundException,
)
from .rename_promote_clone_impl import clone_impl, CloneArgs, rename_impl, RenameArgs
from .snapshot_count_impl import count_snapshots_impl
from .snapshot_create_impl import create_snapshots_impl, CreateSnapshotArgs
from .snapshot_hold_release_impl import hold_impl, HoldArgs, release_impl, ReleaseArgs
from .snapshot_rollback_impl import rollback_impl, RollbackArgs
from .snapshot_query_impl import query_snapshots_impl
from .utils import group_paths_by_parents, has_internal_path, open_resource


class ZFSResourceSnapshotService(Service):
    class Config:
        namespace = "zfs.resource.snapshot"
        cli_private = True
        entry = ZFSResourceSnapshotEntry

    @private
    def validate_recursive_paths(self, schema: str, data: dict):
        """Validate paths don't overlap when recursive=True.

        (Duplicate paths are already rejected by Pydantic UniqueList)
        """
        if not data.get("recursive", False):
            return

        # When recursive, check for overlapping dataset paths
        # (snapshot paths like "tank@snap" are direct lookups, not recursive)
        paths = data.get("paths", [])
        dataset_paths = [p for p in paths if "@" not in p]
        if group_paths_by_parents(dataset_paths):
            raise ValidationError(
                schema,
                (
                    "Paths must be non-overlapping - no path can be relative to another "
                    "when recursive is set to True."
                ),
            )

    @private
    @pass_thread_local_storage
    def query_impl(self, tls, data: dict | None = None):
        base = ZFSResourceSnapshotQueryArgs().model_dump()["data"]
        if data is None:
            final = base
        else:
            final = base | data

        return query_snapshots_impl(tls.lzh, final)

    @api_method(
        ZFSResourceSnapshotQueryArgs,
        ZFSResourceSnapshotQueryResult,
        roles=["SNAPSHOT_READ"],
    )
    def query(self, data):
        """
        This method provides an interface for retrieving information about ZFS snapshots,
        including their properties and user properties.

        Args:
            data: Query parameters containing:
                - paths: List of dataset or snapshot paths to query. If empty, queries all.
                - properties: List of ZFS properties to retrieve. Empty list = defaults, None = none.
                - get_user_properties: Whether to include user-defined properties.
                - get_source: Whether to include property source information.
                - recursive: Include snapshots from child datasets.
                - min_txg: Minimum transaction group filter (0 = no minimum).
                - max_txg: Maximum transaction group filter (0 = no maximum).

        Returns:
            List of snapshot entries with requested properties.

        Examples:
            # Query all snapshots
            query({})

            # Query snapshots for a specific dataset
            query({"paths": ["tank/data"]})

            # Query a specific snapshot
            query({"paths": ["tank/data@backup"]})

            # Query with recursion and specific properties
            query({
                "paths": ["tank"],
                "recursive": True,
                "properties": ["used", "referenced", "creation"]
            })
        """
        self.validate_recursive_paths("zfs.resource.snapshot.query", data)
        try:
            return self.middleware.call_sync("zfs.resource.snapshot.query_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.query", e.message, errno.ENOENT
            )

    @private
    @pass_thread_local_storage
    def count_impl(self, tls, data: dict | None = None):
        base = ZFSResourceSnapshotCountArgs().model_dump()["data"]
        if data is None:
            final = base
        else:
            final = base | data

        return count_snapshots_impl(tls, final)

    @api_method(
        ZFSResourceSnapshotCountArgs,
        ZFSResourceSnapshotCountResult,
        roles=["SNAPSHOT_READ"],
    )
    def count(self, data):
        """
        Count ZFS snapshots per dataset.

        This method provides a fast way to count snapshots without retrieving
        full snapshot information. Useful for UI displays and quota checks.

        Args:
            data: Count parameters containing:
                - paths: List of dataset paths to count snapshots for. If empty,
                         counts snapshots for root filesystems only.
                - recursive: Include snapshots from child datasets in counts.

        Returns:
            Dict mapping dataset names to their snapshot counts.

        Examples:
            # Count snapshots for root filesystems only
            count({})

            # Count all snapshots recursively
            count({"recursive": True})

            # Count snapshots for a specific dataset
            count({"paths": ["tank/data"]})

            # Count snapshots for a dataset and all children
            count({"paths": ["tank"], "recursive": True})
        """
        self.validate_recursive_paths("zfs.resource.snapshot.count", data)
        try:
            return self.middleware.call_sync("zfs.resource.snapshot.count_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.count", e.message, errno.ENOENT
            )

    @private
    @pass_thread_local_storage
    def destroy_impl(self, tls, data: dict):
        schema = "zfs.resource.snapshot.destroy"
        path = data["path"]
        bypass = data.get("bypass", False)

        # Check for internal path protection
        # For snapshot paths, extract the dataset portion
        check_path = path.split("@")[0] if "@" in path else path
        if not bypass and has_internal_path(check_path):
            raise ValidationError(schema, f"{path!r} is a protected path.", errno.EACCES)

        args: DestroyArgs = {
            "path": path,
            "recursive": data.get("recursive", False),
            "all_snapshots": data.get("all_snapshots", False),
            "bypass": bypass,
            "defer": data.get("defer", False),
        }
        return destroy_impl(tls, args)

    @api_method(
        ZFSResourceSnapshotDestroyArgs,
        ZFSResourceSnapshotDestroyResult,
        roles=["SNAPSHOT_DELETE"],
    )
    def destroy(self, data):
        """
        Destroy ZFS snapshots.

        Args:
            data: Destroy parameters containing:
                - path: Snapshot path (e.g., 'pool/dataset@snapshot') or dataset path
                        when all_snapshots=True (e.g., 'pool/dataset').
                - recursive: Recursively destroy matching snapshots in child datasets.
                - all_snapshots: If True, path is a dataset and all its snapshots are destroyed.
                - defer: Defer destruction if snapshot is in use (e.g., has clones).

        Returns:
            None on success.

        Raises:
            ValidationError: If snapshot not found, has clones (without defer), or has holds.

        Examples:
            # Destroy a single snapshot
            destroy({"path": "tank/data@backup"})

            # Destroy recursively (all matching child snapshots)
            destroy({"path": "tank@backup", "recursive": True})

            # Defer destruction if in use
            destroy({"path": "tank/data@snap", "defer": True})

            # Destroy all snapshots for a dataset
            destroy({"path": "tank/data", "all_snapshots": True})

            # Destroy all snapshots for a dataset and its children
            destroy({"path": "tank", "all_snapshots": True, "recursive": True})
        """
        path = data["path"]
        all_snapshots = data.get("all_snapshots", False)

        # Validate path format based on all_snapshots flag
        if all_snapshots:
            if "@" in path:
                raise ValidationError(
                    "zfs.resource.snapshot.destroy",
                    "When all_snapshots is True, path must be a dataset path (no '@').",
                )
        else:
            if "@" not in path:
                raise ValidationError(
                    "zfs.resource.snapshot.destroy",
                    "Path must be a snapshot path (containing '@'). "
                    "Use all_snapshots=True to destroy all snapshots for a dataset.",
                )

        try:
            failed, errnum = self.middleware.call_sync(
                "zfs.resource.snapshot.destroy_impl", data
            )
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.destroy", e.message, errno.ENOENT
            )
        except ZFSPathHasClonesException as e:
            raise ValidationError(
                "zfs.resource.snapshot.destroy", e.message, errno.EBUSY
            )
        except ZFSPathHasHoldsException as e:
            raise ValidationError(
                "zfs.resource.snapshot.destroy", e.message, errno.EBUSY
            )

        if failed:
            raise ValidationError(
                "zfs.resource.snapshot.destroy", failed, errnum or errno.EFAULT
            )

    @private
    @pass_thread_local_storage
    def rename_impl(self, tls, data: dict):
        schema = "zfs.resource.snapshot.rename"
        current_name = data["current_name"]
        bypass = data.get("bypass", False)

        # Check for internal path protection
        # For snapshot paths, extract the dataset portion
        check_path = current_name.split("@")[0] if "@" in current_name else current_name
        if not bypass and has_internal_path(check_path):
            raise ValidationError(schema, f"{current_name!r} is a protected path.", errno.EACCES)

        args: RenameArgs = {
            "current_name": current_name,
            "new_name": data["new_name"],
            "recursive": data.get("recursive", False),
        }
        return rename_impl(tls, args)

    @api_method(
        ZFSResourceSnapshotRenameArgs,
        ZFSResourceSnapshotRenameResult,
        roles=["SNAPSHOT_WRITE"],
    )
    def rename(self, data):
        """
        Rename a ZFS snapshot.

        Args:
            data: Rename parameters containing:
                - current_name: Current snapshot path (e.g., 'pool/dataset@old_name').
                - new_name: New snapshot path (e.g., 'pool/dataset@new_name').
                - recursive: Recursively rename matching snapshots in child datasets.

        Returns:
            None on success.

        Raises:
            ValidationError: If snapshot not found, new name already exists, or invalid paths.

        Examples:
            # Rename a single snapshot
            rename({"current_name": "tank/data@old", "new_name": "tank/data@new"})

            # Rename recursively (all matching child snapshots)
            rename({
                "current_name": "tank@old",
                "new_name": "tank@new",
                "recursive": True
            })
        """
        current_name = data["current_name"]
        new_name = data["new_name"]

        # Validate both paths are snapshot paths
        if "@" not in current_name:
            raise ValidationError(
                "zfs.resource.snapshot.rename",
                "current_name must be a snapshot path (containing '@').",
            )
        if "@" not in new_name:
            raise ValidationError(
                "zfs.resource.snapshot.rename",
                "new_name must be a snapshot path (containing '@').",
            )

        # Validate same dataset (only snapshot name can change)
        current_ds = current_name.rsplit("@", 1)[0]
        new_ds = new_name.rsplit("@", 1)[0]
        if current_ds != new_ds:
            raise ValidationError(
                "zfs.resource.snapshot.rename",
                "Cannot rename snapshot to a different dataset. "
                f"Dataset must remain '{current_ds}'.",
            )

        try:
            self.middleware.call_sync("zfs.resource.snapshot.rename_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.rename", e.message, errno.ENOENT
            )
        except ZFSPathAlreadyExistsException as e:
            raise ValidationError(
                "zfs.resource.snapshot.rename", e.message, errno.EEXIST
            )

    @private
    @pass_thread_local_storage
    def clone_impl(self, tls, data: dict):
        schema = "zfs.resource.snapshot.clone"
        snapshot = data["snapshot"]
        dataset = data["dataset"]
        bypass = data.get("bypass", False)

        # Check for internal path protection on BOTH source and destination
        if not bypass:
            # For snapshot paths, extract the dataset portion
            source_check = snapshot.split("@")[0] if "@" in snapshot else snapshot
            if has_internal_path(source_check):
                raise ValidationError(schema, f"{snapshot!r} is a protected path.", errno.EACCES)
            if has_internal_path(dataset):
                raise ValidationError(schema, f"{dataset!r} is a protected path.", errno.EACCES)

        args: CloneArgs = {
            "current_name": snapshot,
            "new_name": dataset,
        }
        if data.get("properties"):
            args["properties"] = data["properties"]
        return clone_impl(tls, args)

    @api_method(
        ZFSResourceSnapshotCloneArgs,
        ZFSResourceSnapshotCloneResult,
        roles=["SNAPSHOT_WRITE"],
    )
    def clone(self, data):
        """
        Clone a ZFS snapshot to create a new dataset.

        Args:
            data: Clone parameters containing:
                - snapshot: Source snapshot path to clone (e.g., 'pool/dataset@snapshot').
                - dataset: Destination dataset path for the clone (e.g., 'pool/clone').
                - properties: Optional ZFS properties to set on the cloned dataset.

        Returns:
            None on success.

        Raises:
            ValidationError: If snapshot not found, destination already exists, or source is not a snapshot.

        Examples:
            # Clone a snapshot to a new dataset
            clone({"snapshot": "tank/data@backup", "dataset": "tank/data_clone"})

            # Clone with properties
            clone({
                "snapshot": "tank/data@backup",
                "dataset": "tank/data_clone",
                "properties": {"compression": "lz4", "quota": "10G"}
            })
        """
        snapshot = data["snapshot"]
        dataset = data["dataset"]

        # Validate snapshot path contains @
        if "@" not in snapshot:
            raise ValidationError(
                "zfs.resource.snapshot.clone",
                "snapshot must be a snapshot path (containing '@').",
            )

        # Validate dataset path does NOT contain @
        if "@" in dataset:
            raise ValidationError(
                "zfs.resource.snapshot.clone",
                "dataset must be a dataset path (not containing '@').",
            )

        try:
            self.middleware.call_sync("zfs.resource.snapshot.clone_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.clone", e.message, errno.ENOENT
            )
        except ZFSPathAlreadyExistsException as e:
            raise ValidationError(
                "zfs.resource.snapshot.clone", e.message, errno.EEXIST
            )
        except ZFSPathNotASnapshotException:
            raise ValidationError(
                "zfs.resource.snapshot.clone",
                f"'{snapshot}' is not a snapshot.",
            )

    @private
    @pass_thread_local_storage
    def create_impl(self, tls, data: dict):
        schema = "zfs.resource.snapshot.create"
        dataset = data["dataset"]
        bypass = data.get("bypass", False)

        # Check for internal path protection
        if not bypass and has_internal_path(dataset):
            raise ValidationError(schema, f"{dataset!r} is a protected path.", errno.EACCES)

        args: CreateSnapshotArgs = {
            "dataset": dataset,
            "name": data["name"],
            "recursive": data.get("recursive", False),
            "exclude": data.get("exclude", []),
        }
        if data.get("user_properties"):
            args["user_properties"] = data["user_properties"]
        return create_snapshots_impl(tls, args)

    @api_method(
        ZFSResourceSnapshotCreateArgs,
        ZFSResourceSnapshotCreateResult,
        roles=["SNAPSHOT_WRITE"],
    )
    def create(self, data):
        """
        Create a ZFS snapshot.

        Args:
            data: Create parameters containing:
                - dataset: Dataset path to snapshot (e.g., 'pool/dataset').
                - name: Snapshot name (the part after @).
                - recursive: Create snapshots recursively for child datasets.
                - exclude: Datasets to exclude when creating recursive snapshots.
                - user_properties: User properties to set on the snapshot.

        Returns:
            Snapshot entry for the created snapshot.

        Raises:
            ValidationError: If dataset not found or snapshot already exists.

        Examples:
            # Create a single snapshot
            create({"dataset": "tank/data", "name": "backup"})

            # Create recursive snapshots
            create({
                "dataset": "tank",
                "name": "backup",
                "recursive": True
            })

            # Create with user properties
            create({
                "dataset": "tank/data",
                "name": "backup",
                "user_properties": {"com.company:backup_type": "daily"}
            })
        """
        dataset = data["dataset"]
        name = data["name"]

        # Validate dataset path does NOT contain @
        if "@" in dataset:
            raise ValidationError(
                "zfs.resource.snapshot.create",
                "dataset must be a dataset path (not containing '@').",
            )

        # Validate snapshot name does NOT contain @
        if "@" in name:
            raise ValidationError(
                "zfs.resource.snapshot.create",
                "name must be a snapshot name (not containing '@').",
            )

        try:
            return self.middleware.call_sync("zfs.resource.snapshot.create_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.create", e.message, errno.ENOENT
            )
        except ZFSPathAlreadyExistsException as e:
            raise ValidationError(
                "zfs.resource.snapshot.create", e.message, errno.EEXIST
            )
        except ValueError as e:
            raise ValidationError(
                "zfs.resource.snapshot.create", str(e), errno.EINVAL
            )

    @private
    @pass_thread_local_storage
    def hold_impl(self, tls, data: dict):
        schema = "zfs.resource.snapshot.hold"
        path = data["path"]
        bypass = data.get("bypass", False)

        # Check for internal path protection
        if not bypass:
            check_path = path.split("@")[0] if "@" in path else path
            if has_internal_path(check_path):
                raise ValidationError(schema, f"{path!r} is a protected path.", errno.EACCES)

        args: HoldArgs = {
            "path": path,
            "tag": data.get("tag", "truenas"),
            "recursive": data.get("recursive", False),
        }
        return hold_impl(tls, args)

    @api_method(
        ZFSResourceSnapshotHoldArgs,
        ZFSResourceSnapshotHoldResult,
        roles=["SNAPSHOT_WRITE"],
    )
    def hold(self, data):
        """
        Create a hold on a ZFS snapshot.

        A hold prevents a snapshot from being destroyed. Multiple holds
        can be placed on a snapshot with different tags.

        Args:
            data: Hold parameters containing:
                - path: Snapshot path to hold (e.g., 'pool/dataset@snapshot').
                - tag: Hold tag name (default: 'truenas').
                - recursive: Apply hold to matching snapshots in child datasets.

        Returns:
            None on success.

        Raises:
            ValidationError: If snapshot not found or hold creation fails.

        Examples:
            # Hold a single snapshot
            hold({"path": "tank/data@backup"})

            # Hold with custom tag
            hold({"path": "tank/data@backup", "tag": "replication"})

            # Hold recursively
            hold({"path": "tank@backup", "recursive": True})
        """
        path = data["path"]

        # Validate path is a snapshot
        if "@" not in path:
            raise ValidationError(
                "zfs.resource.snapshot.hold",
                "path must be a snapshot path (containing '@').",
            )

        try:
            self.middleware.call_sync("zfs.resource.snapshot.hold_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.hold", e.message, errno.ENOENT
            )
        except ValueError as e:
            raise ValidationError(
                "zfs.resource.snapshot.hold", str(e), errno.EINVAL
            )

    @private
    @pass_thread_local_storage
    def holds_impl(self, tls, path: str) -> tuple:
        rsrc = open_resource(tls, path)
        return rsrc.get_holds()

    @api_method(
        ZFSResourceSnapshotHoldsArgs,
        ZFSResourceSnapshotHoldsResult,
        roles=["SNAPSHOT_READ"],
    )
    def holds(self, data):
        """
        Get holds on a ZFS snapshot.

        Args:
            data: Query parameters containing:
                - path: Snapshot path to query (e.g., 'pool/dataset@snapshot').

        Returns:
            List of hold tag names on the snapshot.

        Examples:
            holds({"path": "tank/data@backup"})
            # Returns: ["truenas", "replication"]
        """
        path = data["path"]

        # Validate path is a snapshot
        if "@" not in path:
            raise ValidationError(
                "zfs.resource.snapshot.holds",
                "path must be a snapshot path (containing '@').",
            )

        try:
            holds = self.middleware.call_sync(
                "zfs.resource.snapshot.holds_impl", path
            )
            return list(holds)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.holds", e.message, errno.ENOENT
            )

    @private
    @pass_thread_local_storage
    def release_impl(self, tls, data: dict):
        schema = "zfs.resource.snapshot.release"
        path = data["path"]
        bypass = data.get("bypass", False)

        # Check for internal path protection
        if not bypass:
            check_path = path.split("@")[0] if "@" in path else path
            if has_internal_path(check_path):
                raise ValidationError(schema, f"{path!r} is a protected path.", errno.EACCES)

        args: ReleaseArgs = {
            "path": path,
            "tag": data.get("tag"),
            "recursive": data.get("recursive", False),
        }
        return release_impl(tls, args)

    @api_method(
        ZFSResourceSnapshotReleaseArgs,
        ZFSResourceSnapshotReleaseResult,
        roles=["SNAPSHOT_WRITE"],
    )
    def release(self, data):
        """
        Release hold(s) from a ZFS snapshot.

        Args:
            data: Release parameters containing:
                - path: Snapshot path to release holds from (e.g., 'pool/dataset@snapshot').
                - tag: Specific hold tag to release. If None, releases all holds.
                - recursive: Release holds from matching snapshots in child datasets.

        Returns:
            None on success.

        Raises:
            ValidationError: If snapshot not found or release fails.

        Examples:
            # Release a specific hold
            release({"path": "tank/data@backup", "tag": "replication"})

            # Release all holds from a snapshot
            release({"path": "tank/data@backup"})

            # Release holds recursively
            release({"path": "tank@backup", "tag": "backup", "recursive": True})
        """
        path = data["path"]

        # Validate path is a snapshot
        if "@" not in path:
            raise ValidationError(
                "zfs.resource.snapshot.release",
                "path must be a snapshot path (containing '@').",
            )

        try:
            self.middleware.call_sync("zfs.resource.snapshot.release_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.release", e.message, errno.ENOENT
            )

    @private
    @pass_thread_local_storage
    def rollback_impl(self, tls, data: dict):
        schema = "zfs.resource.snapshot.rollback"
        path = data["path"]
        bypass = data.get("bypass", False)

        # Check for internal path protection
        if not bypass:
            check_path = path.split("@")[0] if "@" in path else path
            if has_internal_path(check_path):
                raise ValidationError(schema, f"{path!r} is a protected path.", errno.EACCES)

        args: RollbackArgs = {
            "path": path,
            "recursive": data.get("recursive", False),
            "recursive_clones": data.get("recursive_clones", False),
            "force": data.get("force", False),
            "recursive_rollback": data.get("recursive_rollback", False),
        }
        return rollback_impl(tls, args)

    @api_method(
        ZFSResourceSnapshotRollbackArgs,
        ZFSResourceSnapshotRollbackResult,
        roles=["SNAPSHOT_WRITE"],
    )
    def rollback(self, data):
        """
        Rollback a ZFS dataset to a snapshot.

        WARNING: This is a destructive change. All data written since the
        target snapshot was taken will be discarded.

        Args:
            data: Rollback parameters containing:
                - path: Snapshot path to rollback to (e.g., 'pool/dataset@snapshot').
                - recursive: Destroy any snapshots and bookmarks more recent than the one specified.
                - recursive_clones: Like recursive, but also destroy any clones.
                - force: Force unmount of any clones.
                - recursive_rollback: Do a complete recursive rollback of each child snapshot.

        Returns:
            None on success.

        Raises:
            ValidationError: If snapshot not found or rollback fails.

        Examples:
            # Basic rollback
            rollback({"path": "tank/data@backup"})

            # Rollback destroying more recent snapshots
            rollback({"path": "tank/data@backup", "recursive": True})

            # Rollback all child datasets
            rollback({"path": "tank@backup", "recursive_rollback": True})
        """
        path = data["path"]

        # Validate path is a snapshot
        if "@" not in path:
            raise ValidationError(
                "zfs.resource.snapshot.rollback",
                "path must be a snapshot path (containing '@').",
            )

        try:
            self.middleware.call_sync("zfs.resource.snapshot.rollback_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.rollback", e.message, errno.ENOENT
            )
        except ValueError as e:
            raise ValidationError(
                "zfs.resource.snapshot.rollback", str(e), errno.EINVAL
            )
