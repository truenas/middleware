import ctypes
import errno

from typing import Any, Generator, Literal, NamedTuple, TypedDict, overload
from .nss_common import get_nss_func, NssError, NssModule, NssOperation, NssReturnCode

GROUP_INIT_BUFLEN = 1024


class Group(ctypes.Structure):
    _fields_ = [
        ("gr_name", ctypes.c_char_p),
        ("gr_passwd", ctypes.c_char_p),
        ("gr_gid", ctypes.c_int),
        ("gr_mem", ctypes.POINTER(ctypes.c_char_p))
    ]


class group_struct(NamedTuple):
    gr_name: str
    gr_gid: int
    gr_mem: list[str]
    source: str


class GroupDict(TypedDict):
    gr_name: str
    gr_gid: int
    gr_mem: list[str]
    source: str


def __parse_nss_result(result: Group, as_dict: bool, module_name: str) -> group_struct | GroupDict | None:
    if result.gr_name is None:
        return None
    name = result.gr_name.decode()
    members: list[str] = []

    i = 0
    while result.gr_mem[i]:
        members.append(result.gr_mem[i].decode())
        i += 1

    if as_dict:
        return GroupDict(
            gr_name=name,
            gr_gid=result.gr_gid,
            gr_mem=members,
            source=module_name
        )

    return group_struct(name, result.gr_gid, members, module_name)


def __getgrnam_r(name: str, result_p: Any, buffer_p: Any, buflen: int, nss_module: NssModule) -> tuple[int, int, Any]:
    """
    enum nss_status _nss_#module#_getgrnam_r(const char *name,
                                             struct group *result,
                                             char *buffer,
                                             size_t buflen,
                                             int *error)
    """
    func = get_nss_func(NssOperation.GETGRNAM, nss_module)
    func.restype = ctypes.c_int
    func.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(Group),
        ctypes.c_char_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_int)
    ]

    err = ctypes.c_int()
    name_bytes = name.encode('utf-8')
    res = func(ctypes.c_char_p(name_bytes), result_p, buffer_p, buflen, ctypes.byref(err))

    return (int(res), err.value, result_p)


def __getgrgid_r(gid: int, result_p: Any, buffer_p: Any, buflen: int, nss_module: NssModule) -> tuple[int, int, Any]:
    """
    enum nss_status _nss_#module#_getgrgid_r(gid_t gid,
                                             struct group *result,
                                             char *buffer,
                                             size_t buflen,
                                             int *error)
    """
    func = get_nss_func(NssOperation.GETGRGID, nss_module)
    func.restype = ctypes.c_int
    func.argtypes = [
        ctypes.c_ulong,
        ctypes.POINTER(Group),
        ctypes.c_char_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_int)
    ]
    err = ctypes.c_int()
    res = func(gid, result_p, buffer_p, buflen, ctypes.byref(err))

    return (int(res), err.value, result_p)


def __getgrent_r(result_p: Any, buffer_p: Any, buflen: int, nss_module: NssModule) -> tuple[int, int, Any]:
    """
    enum nss_status _nss_#module#_getgrent_r(struct group *result,
                                             char *buffer,
                                             size_t buflen,
                                             int *error)
    """
    func = get_nss_func(NssOperation.GETGRENT, nss_module)
    func.restype = ctypes.c_int
    func.argtypes = [
        ctypes.POINTER(Group),
        ctypes.c_char_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_int)
    ]

    err = ctypes.c_int()
    res = func(result_p, buffer_p, buflen, ctypes.byref(err))

    return (int(res), err.value, result_p)


def __setgrent(nss_module: NssModule) -> None:
    """
    enum nss_status _nss_#module#_setgrent(void)
    """
    func = get_nss_func(NssOperation.SETGRENT, nss_module)
    func.argtypes = []

    res = func()

    if res != NssReturnCode.SUCCESS:
        raise NssError(ctypes.get_errno(), NssOperation.SETGRENT, res, nss_module)


def __endgrent(nss_module: NssModule) -> None:
    """
    enum nss_status _nss_#module#_endgrent(void)
    """
    func = get_nss_func(NssOperation.ENDGRENT, nss_module)
    func.argtypes = []

    res = func()

    if res != NssReturnCode.SUCCESS:
        raise NssError(ctypes.get_errno(), NssOperation.ENDGRENT, res, nss_module)


def __getgrent_impl(
        mod: NssModule,
        as_dict: bool,
        buffer_len: int = GROUP_INIT_BUFLEN
) -> group_struct | GroupDict | None:
    result = Group()

    buf = ctypes.create_string_buffer(buffer_len)

    res, error, result_p = __getgrent_r(ctypes.byref(result), buf,
                                        buffer_len, mod)

    match error:
        case 0:
            pass
        case errno.ERANGE:
            # Our buffer was too small, increment
            return __getgrent_impl(mod, as_dict, buffer_len * 2)
        case _:
            raise NssError(error, NssOperation.GETGRENT, NssReturnCode(res), mod)

    if res != NssReturnCode.SUCCESS:
        return None

    return  __parse_nss_result(result, as_dict, mod.name)


def __getgrall_impl(module: str, as_dict: bool) -> list[group_struct | GroupDict]:
    mod = NssModule[module]
    __setgrent(mod)
    group_list = []

    while group := __getgrent_impl(mod, as_dict):
        group_list.append(group)

    __endgrent(mod)
    return group_list


def __getgrnam_impl(
        name: str,
        module: str,
        as_dict: bool,
        buffer_len: int = GROUP_INIT_BUFLEN
) -> group_struct | GroupDict | None:
    mod = NssModule[module]
    result = Group()

    buf = ctypes.create_string_buffer(buffer_len)

    res, error, result_p = __getgrnam_r(name, ctypes.byref(result),
                                        buf, buffer_len, mod)
    match error:
        case 0:
            pass
        case errno.ERANGE:
            # Our buffer was too small, increment
            return __getgrnam_impl(name, module, as_dict, buffer_len * 2)
        case _:
            raise NssError(error, NssOperation.GETGRNAM, NssReturnCode(res), mod)

    if res == NssReturnCode.NOTFOUND:
        return None

    return  __parse_nss_result(result, as_dict, mod.name)


def __getgrgid_impl(
        gid: int,
        module: str,
        as_dict: bool,
        buffer_len: int = GROUP_INIT_BUFLEN
) -> group_struct | GroupDict | None:
    mod = NssModule[module]
    result = Group()
    buf = ctypes.create_string_buffer(buffer_len)

    res, error, result_p = __getgrgid_r(gid, ctypes.byref(result),
                                        buf, buffer_len, mod)
    match error:
        case 0:
            pass
        case errno.ERANGE:
            # Our buffer was too small, increment
            return __getgrgid_impl(gid, module, as_dict, buffer_len * 2)
        case _:
            raise NssError(error, NssOperation.GETGRGID, NssReturnCode(res), mod)

    if res == NssReturnCode.NOTFOUND:
        return None

    return  __parse_nss_result(result, as_dict, mod.name)


@overload
def getgrgid(gid: int, module: str = ..., *, as_dict: Literal[True]) -> GroupDict: ...


@overload
def getgrgid(gid: int, module: str = ..., as_dict: Literal[False] = False) -> group_struct: ...


def getgrgid(gid: int, module: str = NssModule.ALL.name, as_dict: bool = False) -> group_struct | GroupDict:
    """
    Return the group database entry for the given group by gid.

    `module` - NSS module from which to retrieve the group
    `as_dict` - return output as a dictionary rather than `struct_group`.
    """
    if module != NssModule.ALL.name:
        if (result := __getgrgid_impl(gid, module, as_dict)):
            return result

        raise KeyError(f"getgrgid(): gid not found: '{gid}'")

    # We're querying all modules
    for mod in NssModule:
        if mod == NssModule.ALL:
            continue

        try:
            if (result := __getgrgid_impl(gid, mod.name, as_dict)):
                return result
        except NssError as e:
            if e.return_code != NssReturnCode.UNAVAIL:
                raise e from None

    raise KeyError(f"getgrgid(): gid not found: '{gid}'")


@overload
def getgrnam(name: str, module: str = ..., *, as_dict: Literal[True]) -> GroupDict: ...


@overload
def getgrnam(name: str, module: str = ..., as_dict: Literal[False] = False) -> group_struct: ...


def getgrnam(name: str, module: str = NssModule.ALL.name, as_dict: bool = False) -> group_struct | GroupDict:
    """
    Return the group database entry for the given group by name.

    `module` - NSS module from which to retrieve the group
    `as_dict` - return output as a dictionary rather than `struct_group`.
    """
    if module != NssModule.ALL.name:
        if (result := __getgrnam_impl(name, module, as_dict)):
            return result

        raise KeyError(f"getgrnam(): name not found: '{name}'")

    # We're querying all modules
    for mod in NssModule:
        if mod == NssModule.ALL:
            continue

        try:
            if (result := __getgrnam_impl(name, mod.name, as_dict)):
                return result
        except NssError as e:
            if e.return_code != NssReturnCode.UNAVAIL:
                raise e from None

    raise KeyError(f"getgrnam(): name not found: '{name}'")


def getgrall(module: str = NssModule.ALL.name, as_dict: bool = False) -> dict[str, list[group_struct | GroupDict]]:
    """
    Returns all group entries on server (similar to grp.getgrall()).

    `module` - NSS module from which to retrieve the entries
    `as_dict` - return password database entries as dictionaries

    This module returns a dictionary keyed by NSS module, e.g.
    {'FILES': [<struct_group>, <struct_group>], 'WINBIND': [], 'SSS': []}
    """
    if module != NssModule.ALL.name:
        return {module: __getgrall_impl(module, as_dict)}

    results = {}
    for mod in NssModule:
        if mod == NssModule.ALL:
            continue

        entries = []
        try:
            entries = __getgrall_impl(mod.name, as_dict)
        except NssError as e:
            if e.return_code != NssReturnCode.UNAVAIL:
                raise e from None

        results[mod.name] = entries

    return results


def itergrp(
        module: str = NssModule.FILES.name,
        as_dict: bool = False
) -> Generator[group_struct | GroupDict, None, None]:
    """
    Generator that yields group entries on server

    `module` - NSS module from which to retrieve the entries
    `as_dict` - yield password database entries as dictionaries

    WARNING: users of this API should not create two generators for
    same passwd database concurrently in the same thread due to NSS
    modules storing the handle for the pwent in thread-local variable:

    BAD:
    iter1 = itergrp(NssModule.FILES.name, True)
    iter2 = itergrp(NssModule.FILES.name, True)
    for x in iter1:
        for y in iter2

    or call getgrall() during iteration

    ALSO BAD:
    iter1 = itergrp(NssModule.FILES.name, True)
    for x in iter1:
        grp = getgrall()
    """
    if module == NssModule.ALL.name:
        raise ValueError('Please select one of: FILES, WINBIND, SSS')

    mod = NssModule[module]
    __setgrent(mod)

    try:
        while group := __getgrent_impl(mod, as_dict):
            yield group
    finally:
        __endgrent(mod)
