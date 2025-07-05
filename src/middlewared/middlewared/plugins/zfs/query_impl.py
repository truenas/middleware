import dataclasses
import itertools

try:
    from truenas_pylibzfs import ZFSError, ZFSException
except ImportError:
    ZFSError = ZFSException = None

from middlewared.utils import BOOT_POOL_NAME_VALID
from .normalization import normalize_asdict_result
from .property_management import build_set_of_zfs_props, DeterminedProperties

__all__ = ("query_impl", "ZFSPathNotFoundException")

INTERNAL_FILESYSTEMS = (
    ".system",
    "ix-applications",
    "ix-apps",
    ".ix-virt",
)


class ZFSPathNotFoundException(Exception):
    pass


@dataclasses.dataclass(slots=True, kw_only=True)
class CallbackState:
    results: list
    query_args: dict
    dp: DeterminedProperties
    eip: bool = False
    short_circuit_filters: dict


def __is_internal_path(path):
    """
    Check if a path is an internal filesystem.

    Args:
        path: relative path representing the zfs filesystem

    Returns:
        bool: True if the path is internal, False otherwise
    """
    for a, b in itertools.zip_longest(BOOT_POOL_NAME_VALID, INTERNAL_FILESYSTEMS):
        if a and (path == a or path.startswith(f"{a}/")):
            return True
        if b and (f"/{b}" in path):
            return True
    return False


def __query_impl_callback(hdl, state):
    if state.eip and __is_internal_path(hdl.name):
        # returning False here will halt the iteration
        # entirely which is not what we want to do
        return True

    for k, v in state.short_circuit_filters.items():
        attr = getattr(hdl, k)
        if k == "type" and state.short_circuit_filters["value"] != attr.name:
            # returning False here will halt the iteration
            # entirely which is not what we want to do because
            # the user is trying to query all resources for
            # a specific type
            return True
        elif state.short_circuit_filters["value"] != attr:
            return True

    state.results.append(
        normalize_asdict_result(
            hdl.asdict(
                properties=build_set_of_zfs_props(
                    hdl.type, state.dp, state.query_args["properties"]
                ),
                get_user_properties=state.query_args["get_user_properties"],
                get_source=state.query_args["get_source"],
            )
        )
    )
    if state.query_args["get_children"]:
        hdl.iter_filesystems(callback=__query_impl_callback, state=state)
    return True


def __query_impl_paths(hdl, state):
    # end-user has provided specific paths
    # to be queried and so we can apply
    # significant optimizations by querying
    # these specific resources without iterating
    # over all filesystems just to find the ones
    # the end-user wants
    for path in state.query_args["paths"]:
        try:
            rsrc = hdl.open_resource(name=path)
            __query_impl_callback(rsrc, state)
        except ZFSException as e:
            if ZFSError(e.code) == ZFSError.EZFS_NOENT:
                raise ZFSPathNotFoundException(f"{path!r}: not found")
            raise


def __query_impl_roots(hdl, state):
    hdl.iter_root_filesystems(callback=__query_impl_callback, state=state)


def __extract_filters(state):
    # Certain incantations of query filters can
    # be given to us that allow us to apply some
    # dramatic optimizations.
    filters = state.query_args["query-filters"]
    if filters and filters[0][1] in ("=", "in"):
        if filters[0][0] in ("name", "pool"):
            extracted = filters.pop(0)
            if isinstance(extracted[2], str):
                # [["name", "=", "tank/foo"]]
                # or
                # [["pool", "=", "tank"]
                state.query_args["paths"].append(extracted[2])
            else:
                # [["name", "in", ["tank/foo", "dozer/foo"]]]
                # or
                # [["pool", "in", ["tank", "dozer"]]]
                state.query_args["paths"].extend(extracted[2])
        elif filters[0][0] in ("type", "guid", "createtxg"):
            # [["type", "=", "ZFS_TYPE_FILESYSTEM"]]
            extracted = filters.pop(0)
            is_enum = extracted[0] == "type"
            if isinstance(extracted[2], str):
                # [["type", "=", "ZFS_TYPE_FILESYSTEM"]]
                state.short_circuit_filters = {
                    extracted[0]: {"value": [extracted[2]], "is_enum": is_enum}
                }
            else:
                # [["type", "in", ["ZFS_TYPE_FILESYSTEM", ...]]]
                state.short_circuit_filters = {
                    extracted[0]: {"value": [extracted[2]], "is_enum": is_enum}
                }


def __should_exclude_internal_paths(state):
    if not state.query_args["paths"]:
        # no paths given, which equates to an
        # "empty" query. ignore internal paths.
        state.eip = True
    else:
        for path in state.query_args["paths"]:
            if __is_internal_path(path):
                # somone is explicilty querying an
                # internal path
                state.eip = False
                break
        else:
            # someone specified path(s) and none
            # are an internal path
            state.eip = True


def query_impl(hdl, data):
    state = CallbackState(
        results=list(),
        query_args=data,
        dp=DeterminedProperties(),
        short_circuit_filters=dict(),
    )
    __extract_filters(state)
    __should_exclude_internal_paths(state)
    if state.query_args["paths"]:
        __query_impl_paths(hdl, state)
    else:
        # if someone queries for zfs resources without
        # applying any type of filters/options/paths etc
        # then we'll be nice and set get_children: True
        # so that it returns some information. Otherwise
        # it's a less than stellar experience
        state.query_args["get_children"] = state.query_args["get_children"] or (
            not state.query_args["query-filters"]
        )
        __query_impl_roots(hdl, state)
    return state.results
