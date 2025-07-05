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
from middlewared.utils import filter_list

from .query_impl import query_impl, ZFSPathNotFoundException


class ZFSResourceService(Service):
    class Config:
        namespace = "zfs.resource"
        cli_private = True
        entry = ZFSResourceEntry

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
                    "Querying snapshot information is unsupported at this time.",
                )

        if data["get_children"] and self.group_paths_by_parents(data["paths"]):
            raise ValidationError(
                "zfs.resource.query",
                (
                    "Paths must be non-overlapping - no path can be relative to another "
                    "when get_children is set to True."
                ),
            )

    @api_method(
        ZFSResourceQueryArgs,
        ZFSResourceQueryResult,
        pass_thread_local_storage=True,
        roles=["FULL_ADMIN"],
    )
    def query(self, tls, data):
        self.validate_query_args(data)
        try:
            return filter_list(
                query_impl(tls.lzh, data),
                data["query-filters"],
                data["query-options"],
            )
        except ZFSPathNotFoundException as e:
            raise ValidationError("zfs.resource.query", str(e), errno.ENOENT)
