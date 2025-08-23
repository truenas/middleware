import errno
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

from .query_impl import query_impl, ZFSPathNotFoundException
from .destroy_impl import destroy_impl
from .utils import has_internal_path


class ZFSResourceService(Service):
    class Config:
        namespace = "zfs.resource"
        cli_private = True
        entry = ZFSResourceEntry

    @private
    def snapshot_exists(self, snap_name: str):
        """Check to see if a given snapshot exists.
        NOTE: internal method so lots of assumptions
        are made by the passed in `snap_name` arg."""
        ds, snap_name = snap_name.split("@")
        rv = self.middleware.call_sync(
            "zfs.resource.query_impl",
            {"paths": [ds], "properties": None, "get_snapshots": True},
        )
        return rv and snap_name in rv[0]["snapshots"]

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
            raise ValidationError("zfs.resource.query", str(e), errno.ENOENT)

    @private
    def validate_and_parse_destroy_args(self, data):
        schema = "zfs.resource.destroy"
        if not data["paths"]:
            raise ValidationError(schema, "One path must be given")

        adip = data.get("allow_destroy_internal_paths", False)
        fs_or_vols, snapshots_temp = list(), list()
        for path in data["paths"]:
            if path[0] == "/" or path[-1] == "/":
                raise ValidationError(
                    schema, f"{path!r} may not begin or end with / character"
                )
            elif "#" in path:
                raise ValidationError(
                    schema, "Destroying bookmarks is unsupported at this time"
                )
            elif "/" not in path:
                if "@" in path and data["recursive"]:
                    raise ValidationError(
                        schema,
                        "Recursively destroying snapshots at root of zpool is not allowed",
                    )
                else:
                    raise ValidationError(
                        schema,
                        "Destroying zpools is not allowed. Use zfs.resource.destroy_pools",
                    )
            elif not adip and has_internal_path(path):
                raise ValidationError(
                    schema, f"{path!r} is a protected path and may not be destroyed"
                )
            elif "@" in path:
                components = path.split("@")
                if len(components) > 2:
                    raise ValidationError(
                        schema, f"Only one @ character is allowed in {path!r}"
                    )
                elif not components[0].strip():
                    raise ValidationError(
                        schema, f"Missing filesystem or volume name in {path!r}"
                    )
                elif not components[-1].strip():
                    raise ValidationError(schema, f"Missing snapshot name in {path!r}")
                else:
                    snapshots_temp.append(path)
            else:
                fs_or_vols.append(path)

        if data["recursive"]:
            err = "Overlapping paths are not allowed when recursive is true"
            for k, v in self.group_paths_by_parents(fs_or_vols).items():
                # 2 things:
                #   1. We'll raise validation error on 1st path that is over-lapping
                #       since trying to be cute here and cram all over-lapping paths
                #       in 1 validation error message doesn't translate very clearly
                #       to the end-user.
                #   2. If someone provides fs/zvols to be recursively deleted, and
                #       any of the paths overlap with one another, then it'll cause
                #       EZFS_NOENT to be raised. We could, in theory, gracefully
                #       handle that on our side but meh.
                raise ValidationError(
                    schema, f"{err} ({k} overlaps with {', '.join(v)})"
                )

        # By the time we're here, basic validation has been performed on the paths
        # and we've separated snapshots from everything else. Now we're going to
        # further separate each snapshot path given to us. Primarily, we need to
        # make sure we parse a simple regex pattern for snapshots that allows users
        # the ability to destroy more than 1 snapshot depending on the flags given
        # to us in the API schema. While we're here, we also check to see if the user
        # has given us a filesystem/zvol path that is also the source for a snapshot.
        # If this happens, there is no reason to try and delete that filesystem/zvol's
        # snapshots because deleting the filesystem/zvol will delete snapshots as well.
        snapshots = {"singular": list(), "channel_programs": list()}
        for i in snapshots_temp:
            snap_source, snap_name = i.split("@")
            if snap_source in fs_or_vols:
                # there is no reason to parse this since all snapshots
                # we'll be deleted by virtue of deleting the resource
                # that the snapshot is associated to.
                continue

            if snap_name != "*" and not data["recursive"]:
                snapshots["singular"].append(path)
            else:
                channel_args = {
                    "path": i,
                    "pool_name": snap_source.split("/")[0],
                    "readonly": False,
                    "script_arguments_dict": {
                        "recursive": data["recursive"],
                        "target": snap_source,
                        "defer": data["defer"],
                    },
                }
                if snap_name != "*":
                    channel_args["script_arguments_dict"].update({"pattern": snap_name})
                snapshots["channel_programs"].append(channel_args)

        data.update({"fs_or_vols": fs_or_vols, "snapshots": snapshots})

    @private
    @pass_thread_local_storage
    def destroy_impl(
        self, tls, data: dict | None = None, allow_destroy_internal_paths: bool = False
    ):
        adip = {"allow_destroy_internal_paths": allow_destroy_internal_paths}
        base = ZFSResourceDestroyArgs().model_dump()["data"]
        if data is None:
            final = base | adip
        else:
            final = base | data | adip
        self.validate_and_parse_destroy_args(final)
        return destroy_impl(tls.lzh, final)

    @api_method(
        ZFSResourceDestroyArgs,
        ZFSResourceDestroyResult,
        roles=["ZFS_RESOURCE_WRITE"]
    )
    def destroy(self, data):
        """
        Destroy ZFS resources (filesystems, volumes, snapshots).

        This method provides a safe interface for destroying ZFS resources with \
        various options for handling dependencies and busy resources. The operation \
        can be configured to handle recursive destruction, forced unmounting, and \
        deferred destruction.

        WARNING: This operation is destructive and cannot be undone. All data \
        in the destroyed resources will be permanently lost.

        Raises:
            ValidationError: If:
                - No paths are specified
                - Invalid path format is provided
                - Overlapping paths are included with recursive=True

        Examples:
            # Destroy a single resource
            destroy({"paths": ["tank/temp"]})

            # Destroy multiple resources
            destroy({"paths": ["tank/temp", "tank/foo"]})

            # Destroy a snapshot and a resource
            destroy({"paths": ["tank/temp", "tank/foo@snap"]})

            # Recursively destroy a dataset and all its children
            destroy({"paths": ["tank/temp"], "recursive": True})

            # Force destroy even if mounted or busy
            destroy({"paths": ["tank/temp"], "force": True})

            # Defer destruction until resource is no longer in use
            destroy({"paths": ["tank/temp"], "defer": True})

            # Destroy a single snapshot
            destroy({"paths": ["tank/temp@snap"]})

            # Destroy multiple snapshots
            destroy({"paths": ["tank/temp@snap1", "tank/temp@snap2"]})

            # Recursively destroy all snapshots named "snap" for all children
            destroy({"paths": ["tank/temp@snap"], "recursive": True})

            # Recursively destroy all snapshots named "snap1" and "snap2"
            # for all children
            destroy({"paths": ["tank/temp@snap1", "tank/temp@snap2"], "recursive": True})

            # Recursively destroy ALL snapshots
            destroy({"paths": ["tank/temp@*"], "recursive": True})

            # Destroy ALL snapshots with out recursing to children
            destroy({"paths": ["tank/temp@*"]})
        """
        return self.middleware.call_sync("zfs.resource.destroy_impl", data)
