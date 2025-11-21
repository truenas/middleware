import errno
import os
import pathlib

from middlewared.api import api_method
from middlewared.api.current import (
    ZFSResourceDestroyArgs,
    ZFSResourceDestroyResult,
    ZFSResourceEntry,
    ZFSResourceQueryArgs,
    ZFSResourceQueryResult,
)
from middlewared.service import Service, private
from middlewared.service_exception import ValidationError
from middlewared.service.decorators import pass_thread_local_storage

from .destroy_impl import destroy_impl, DestroyArgs
from .exceptions import (
    ZFSPathAlreadyExistsException,
    ZFSPathHasClonesException,
    ZFSPathHasHoldsException,
    ZFSPathInvalidException,
    ZFSPathNotASnapshotException,
    ZFSPathNotFoundException,
    ZFSPathNotProvidedException,
)
from .load_unload_impl import unload_key_impl, UnloadKeyArgs
from .mount_unmount_impl import (
    mount_impl,
    MountArgs,
    unmount_impl,
    UnmountArgs,
)
from .query_impl import query_impl
from .rename_promote_clone_impl import (
    clone_impl,
    CloneArgs,
    promote_impl,
    PromoteArgs,
    rename_impl,
    RenameArgs,
)
from .utils import has_internal_path


class ZFSResourceService(Service):
    class Config:
        namespace = "zfs.resource"
        cli_private = True
        entry = ZFSResourceEntry

    @private
    @pass_thread_local_storage
    def clone(self, tls, data: CloneArgs) -> None:
        schema = "zfs.resource.clone"
        try:
            clone_impl(tls, data)
        except ZFSPathNotASnapshotException:
            raise ValidationError(schema, "Only snapshots may be cloned")
        except ZFSPathAlreadyExistsException as e:
            raise ValidationError(schema, e.message, errno.EEXIST)
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'current_name' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    @pass_thread_local_storage
    def promote(self, tls, data: PromoteArgs) -> None:
        schema = "zfs.resource.promote"
        try:
            promote_impl(tls, data)
        except ZFSPathInvalidException:
            raise ValidationError(schema, f"{data['current_name']!r} is ineligible for promotion.")
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'current_name' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    @pass_thread_local_storage
    def mount(self, tls, data: MountArgs) -> None:
        schema = "zfs.resource.mount"
        try:
            mount_impl(tls, data)
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'filesystem' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    @pass_thread_local_storage
    def unmount(self, tls, data: UnmountArgs) -> None:
        schema = "zfs.resource.unmount"
        try:
            unmount_impl(tls, data)
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'filesystem' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    @pass_thread_local_storage
    def unload_key(self, tls, data: UnloadKeyArgs) -> None:
        schema = "zfs.resource.unload_key"
        try:
            unload_key_impl(tls, data)
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'filesystem' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    @pass_thread_local_storage
    def rename(self, tls, data: RenameArgs) -> None:
        schema = "zfs.resource.rename"
        try:
            rename_impl(tls, data)
        except ZFSPathNotASnapshotException:
            raise ValidationError(schema, "recursive is only valid for snapshots")
        except ZFSPathAlreadyExistsException as e:
            raise ValidationError(schema, e.message, errno.EEXIST)
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'current_name' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    def group_paths_by_parents(self, paths: list[str]) -> dict[str, list[str]]:
        """
        Group paths by their parent directories, mapping each parent to
        all paths that are relative to it. For each path in the input list,
        finds all other paths that are relative to that path and groups
        them together.

        Args:
            paths: List of relative POSIX path strings

        Returns:
            Dict mapping parent paths to lists of their relative subpaths

        Example:
            >>> group_paths_by_parents(['dozer/test', 'dozer/test/foo', 'tank', 'dozer/abc'])
            {'dozer/test': ['dozer/test/foo']}
        """
        root_dict = dict()
        if not paths:
            return root_dict

        for path in paths:
            subpaths = list()
            for sp in paths:
                if pathlib.Path(sp).is_relative_to(pathlib.Path(path)) and sp != path:
                    # Find all paths that are relative to this path
                    # (excluding the path itself)
                    subpaths.append(sp)
            if subpaths:
                root_dict[path] = subpaths
        return root_dict

    @private
    def validate_query_args(self, data):
        for path in data["paths"]:
            if "@" in path:
                raise ValidationError(
                    "zfs.resource.query",
                    "Set `get_snapshots = True` when wanting to query snapshot information.",
                )

        if data["get_children"] and self.group_paths_by_parents(data["paths"]):
            raise ValidationError(
                "zfs.resource.query",
                (
                    "Paths must be non-overlapping - no path can be relative to another "
                    "when get_children is set to True."
                ),
            )

    @private
    def nest_paths(self, flat_list: dict) -> list[dict]:
        """
        Convert a flat list of dictionaries with path-like
        names into a nested tree structure. Nodes are attached
        to their nearest existing ancestor. If no ancestor
        exists, they become root nodes.

        Args:
            flat_list: List of dictionaries with, minimally, the
            following top-level keys 'name', 'pool', and 'children'.

        Returns:
            List containing the root nodes with nested children
        """
        node_map = {}
        roots = []
        # first pass is to create index
        for item in flat_list:
            node_map[item["name"]] = item
            if item["name"] == item["pool"]:
                # root filesystem (zpool)
                roots.append(item)
                continue

        # second pass establishes parent/child relationship
        # NOTE: the 2nd iteration is necessary
        # because the list being passed in is not
        # guaranteed to be in heirarchical order
        for item in flat_list:
            if item["name"] == item["pool"]:
                continue
            for parent in pathlib.PosixPath(item["name"]).parents:
                pap = parent.as_posix()
                if pap in node_map:
                    node_map[pap]["children"].append(item)
                    break
            else:
                # If no parent exists, this is a root
                roots.append(item)
        return roots

    @private
    @pass_thread_local_storage
    def query_impl(self, tls, data: dict | None = None):
        base = ZFSResourceQueryArgs().model_dump()["data"]
        if data is None:
            final = base
        else:
            final = base | data
            self.validate_query_args(final)

        results = query_impl(tls.lzh, final)
        if final["nest_results"]:
            return self.nest_paths(results)
        else:
            return results

    @private
    def snapshot_exists(self, snap_name: str):
        """Check to see if a given snapshot exists.
        NOTE: internal method so lots of assumptions
        are made by the passed in `snap_name` arg."""
        rv = self.middleware.call_sync(
            "zfs.resource.query_impl",
            {
                "paths": [snap_name.split("@")[0]],
                "properties": None,
                "get_snapshots": True,
            },
        )
        return rv and snap_name in rv[0]["snapshots"]

    @private
    @pass_thread_local_storage
    def destroy_impl(self, tls, data: DestroyArgs):
        schema = "zfs.resource.destroy"
        path = data["path"]
        data.setdefault("recursive", False)
        data.setdefault("bypass", False)
        data.setdefault("all_snapshots", False)
        if os.path.isabs(path):
            raise ValidationError(
                schema, "Absolute path is invalid. Must be in form of <pool>/<resource>.", errno.EINVAL
            )
        elif path.endswith("/"):
            raise ValidationError(schema, "Path must not end with a forward-slash.", errno.EINVAL)
        elif not data["bypass"] and has_internal_path(path):
            # NOTE: `bypass` is a value only exposed to
            # internal callers and not to our public API.
            raise ValidationError(schema, f"{path!r} is a protected path.", errno.EACCES)

        a_snapshot = "@" in path

        if not a_snapshot:
            tmp = path.split("/")
            if len(tmp) == 1 or tmp[-1] == "":
                raise ValidationError(schema, "Destroying the root filesystem is not allowed.", errno.EINVAL)

        if a_snapshot and data["all_snapshots"]:
            raise ValidationError(
                schema,
                f"Setting all_snapshots and specifying a snapshot ({path}) is invalid.",
                errno.EINVAL,
            )

        if not data["recursive"]:
            if not a_snapshot:
                args = {"paths": [path], "properties": None, "get_children": True, "get_snapshots": True}
                rv = self.middleware.call_sync("zfs.resource.query", args)
                extra = "Set recursive=True to remove them."
                if not rv:
                    raise ValidationError(schema, f"{path!r} does not exist.", errno.ENOENT)
                elif len(rv) > 1:
                    raise ValidationError(schema, f"{path!r} has children. {extra}", errno.ENOTEMPTY)
                elif not data["all_snapshots"] and rv[0]["snapshots"]:
                    raise ValidationError(schema, f"{path!r} has snapshots. {extra}", errno.ENOTEMPTY)

        return destroy_impl(tls, data)

    @api_method(
        ZFSResourceDestroyArgs,
        ZFSResourceDestroyResult,
        roles=["ZFS_RESOURCE_WRITE"]
    )
    def destroy(self, data):
        """
        Destroy a ZFS resource (filesystem, volume, or snapshot).

        This method provides an interface for destroying ZFS resources with support \
        for recursive deletion, clone removal, hold removal, and batch snapshot deletion.

        Args:
            data (dict): Dictionary containing destruction parameters:
                - path (str): Path of the ZFS resource to destroy. Must be in the form \
                    'pool/name', 'pool/name@snapshot', or 'pool/zvol'.
                    Cannot be an absolute path or end with a forward slash.
                - recursive (bool, optional): If True, recursively destroy all descendants.
                    For snapshots, destroys the snapshot across all descendant resources and \
                    also destroy clones and/or holds that may be present.
                    Default: False.
                - all_snapshots (bool, optional): If True, destroy all snapshots of the \
                    specified resource (resource remains). Default: False.

        Returns:
            None: On successful destruction.

        Raises:
            ValidationError: Raised in the following cases:
                - Resource does not exist (ENOENT)
                - Resource has children and recursive=False (EBUSY)
                - Attempting to destroy root filesystem
                - Path is absolute (starts with /)
                - Path ends with forward slash
                - Path references protected internal resources

        Examples:
            # Destroy a simple filesystem
            destroy({"path": "tank/temp"})

            # Recursively destroy filesystem, snapshots, clones, holds
            # and all children
            destroy({"path": "tank/parent", "recursive": True})

            # Destroy a specific snapshot
            destroy({"path": "tank/temp@snapshot1"})

            # Recursively destroy the snapshot across all descendant
            # resources including clone(s), and/or hold(s)
            destroy({"path": "tank/parent@snap", "recursive": True})

            # Destroy all snapshots of a resource (keeping "tank/temp")
            destroy({"path": "tank/temp", "all_snapshots": True})

        Notes:
            - Root filesystem destruction is not allowed for safety
            - Protected system paths cannot be destroyed via API
            - When destroying snapshots recursively, only matching snapshots in
              descendant datasets are removed
            - The all_snapshots flag only removes snapshots, not the dataset itself
            - For volumes with snapshots, either use recursive=True or all_snapshots=True
        """
        schema = "zfs.resource.destroy"
        data = DestroyArgs(**data)
        data["bypass"] = False
        try:
            failed, errnum = self.middleware.call_sync("zfs.resource.destroy_impl", data)
        except (ZFSPathHasClonesException, ZFSPathHasHoldsException) as e:
            raise ValidationError(schema, e.message, errno.ENOTEMPTY)
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)
        else:
            if failed:
                # this is the channel program execution path and so when an
                # error is raised while executing a channel program, the
                # handling of errors is done a bit differently since the
                # operation is done atomically behind the scenes. This should
                # only be happening if someone is recursively deleting a
                # resource.
                raise ValidationError(schema, failed, errnum)

    @api_method(
        ZFSResourceQueryArgs,
        ZFSResourceQueryResult,
        roles=["ZFS_RESOURCE_READ"],
    )
    def query(self, data):
        """
        Query ZFS resources (datasets and volumes) with flexible filtering options.

        This method provides a high-performance interface for retrieving information \
        about ZFS resources, including their properties, hierarchical relationships, \
        and metadata. The query can be customized to retrieve specific resources, \
        properties, and control the output format.

        Raises:
            ValidationError: If:
                - Snapshot paths are provided (must use `get_snapshots = True`)
                - Overlapping paths are provided with get_children=True

        Examples:
            # Query all resources with default properties
            query()

            # Query specific resources with all properties
            query({"paths": ["tank/documents", "tank/media"]})

            # Query with specific properties and children
            query({
                "paths": ["tank"],
                "properties": ["mounted", "compression", "used"],
                "get_children": True
            })

            # Get hierarchical view of resources
            query({"paths": ["tank"], "nest_results": True, "get_children": True})
        """
        try:
            return self.middleware.call_sync("zfs.resource.query_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError("zfs.resource.query", e.message, errno.ENOENT)
