import dataclasses

try:
    from truenas_pylibzfs import ZFSError, ZFSException
except ImportError:
    ZFSError = ZFSException = None

from .normalization import normalize_asdict_result
from .property_management import build_set_of_zfs_props, DeterminedProperties
from .utils import has_internal_path

__all__ = ("query_impl", "ZFSPathNotFoundException")


class ZFSPathNotFoundException(Exception):
    pass


@dataclasses.dataclass(slots=True, kw_only=True)
class CallbackState:
    results: list
    query_args: dict
    dp: DeterminedProperties
    eip: bool
    """(e)xclude (i)nternal (p)aths. Unless
    someone is querying an internal path, we
    will exclude them."""


def __query_impl_callback(hdl, state):
    if state.eip and has_internal_path(hdl.name):
        # returning False here will halt the iteration
        # entirely which is not what we want to do
        return True

    state.results.append(
        normalize_asdict_result(
            hdl.asdict(
                properties=build_set_of_zfs_props(
                    hdl.type, state.dp, state.query_args["properties"]
                ),
                get_user_properties=state.query_args["get_user_properties"],
                get_source=state.query_args["get_source"],
            ),
            normalize_source=state.query_args["get_source"],
        )
    )
    if state.query_args["get_children"]:
        hdl.iter_filesystems(callback=__query_impl_callback, state=state)
    return True


def __query_impl_paths(hdl, state):
    for path in state.query_args["paths"]:
        try:
            rsrc = hdl.open_resource(name=path)
            __query_impl_callback(rsrc, state)
        except ZFSException as e:
            if ZFSError(e.code) == ZFSError.EZFS_NOENT:
                if state.query_args.get("raise_on_noent", False):
                    raise ZFSPathNotFoundException(f"{path!r}: not found")
                else:
                    continue
            raise


def __query_impl_roots(hdl, state):
    hdl.iter_root_filesystems(callback=__query_impl_callback, state=state)


def __should_exclude_internal_paths(data):
    for path in data["paths"]:
        if has_internal_path(path):
            # somone is explicilty querying an
            # internal path
            return False
    # 1. no paths specified are internal path
    # 2. no paths specified at all (empty query)
    # 3. or someone exclusively asks for internal paths
    #   NOTE: (the `exclude_internal_paths` is a private
    #   internal argument that is set internally within
    #   middleware. It's not exposed to public.)
    return data.get('exclude_internal_paths', True)


def query_impl(hdl, data):
    state = CallbackState(
        results=list(),
        query_args=data,
        dp=DeterminedProperties(),
        eip=__should_exclude_internal_paths(data),
    )
    if state.query_args["paths"]:
        __query_impl_paths(hdl, state)
    else:
        __query_impl_roots(hdl, state)
    return state.results
