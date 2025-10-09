import errno
import pathlib

from middlewared.api import api_method
from middlewared.api.current import (
    ZFSResourceEntry,
    ZFSResourceQueryArgs,
    ZFSResourceQueryResult,
)
from middlewared.service import Service, private
from middlewared.service_exception import ValidationError
from middlewared.service.decorators import pass_thread_local_storage

from .exceptions import (
    ZFSPathNotFoundException,
    ZFSPathNotProvidedException,
    ZFSRenamePathAlreadyExistsException,
    ZFSRenameNotASnapshotException,
    ZFSRenamePathNotProvidedException,
)
from .load_unload_impl import unload_key_impl, UnloadKeyArgs
from .mount_unmount_impl import (
    mount_impl,
    MountArgs,
    unmount_impl,
    UnmountArgs,
)
from .rename_promote_inherit_impl import rename_impl, RenameArgs
from .query_impl import query_impl


class ZFSResourceService(Service):
    class Config:
        namespace = "zfs.resource"
        cli_private = True
        entry = ZFSResourceEntry

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
        except ZFSRenameNotASnapshotException:
            raise ValidationError(schema, "recursive is only valid for snapshots")
        except ZFSRenamePathNotProvidedException:
            raise ValidationError(schema, "'new_name' key is required")
        except ZFSRenamePathAlreadyExistsException as e:
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
