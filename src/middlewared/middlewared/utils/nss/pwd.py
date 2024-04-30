import ctypes
import errno

from collections import namedtuple
from .nss_common import get_nss_func, NssError, NssModule, NssOperation, NssReturnCode

PASSWD_INIT_BUFLEN = 1024


class Passwd(ctypes.Structure):
    _fields_ = [
        ("pw_name", ctypes.c_char_p),
        ("pw_passwd", ctypes.c_char_p),
        ("pw_uid", ctypes.c_int),
        ("pw_gid", ctypes.c_int),
        ("pw_gecos", ctypes.c_char_p),
        ("pw_dir", ctypes.c_char_p),
        ("pw_shell", ctypes.c_char_p)
    ]


pwd_struct = namedtuple('struct_passwd', [
    'pw_name', 'pw_uid', 'pw_gid', 'pw_gecos', 'pw_dir', 'pw_shell', 'source'
])


def __parse_nss_result(result, as_dict, module_name):
    name = result.pw_name.decode()
    gecos = result.pw_gecos.decode()
    homedir = result.pw_dir.decode()
    shell = result.pw_shell.decode()

    if as_dict:
        return {
            'pw_name': name,
            'pw_uid': result.pw_uid,
            'pw_gid': result.pw_gid,
            'pw_gecos': gecos,
            'pw_dir': homedir,
            'pw_shell': shell,
            'source': module_name
        }

    return pwd_struct(name, result.pw_uid, result.pw_gid, homedir, gecos, shell, module_name)


def __getpwnam_r(name, result_p, buffer_p, buflen, nss_module):
    """
    enum nss_status _nss_#module#_getpwnam_r(const char *name,
                                             struct passwd *result,
                                             char *buffer,
                                             size_t buflen,
                                             int *errnop)
    """
    func = get_nss_func(NssOperation.GETPWNAM, nss_module)
    func.restype = ctypes.c_int
    func.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(Passwd),
        ctypes.c_char_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_int)
    ]

    err = ctypes.c_int()
    name = name.encode('utf-8')
    res = func(ctypes.c_char_p(name), result_p, buffer_p, buflen, ctypes.byref(err))

    return (int(res), err.value, result_p)


def __getpwuid_r(uid, result_p, buffer_p, buflen, nss_module):
    """
    enum nss_status _nss_#module#_getpwuid_r(uid_t uid,
                                             struct passwd *result,
                                             char *buffer,
                                             size_t buflen,
                                             int *errnop)
    """
    func = get_nss_func(NssOperation.GETPWUID, nss_module)
    func.restype = ctypes.c_int
    func.argtypes = [
        ctypes.c_ulong,
        ctypes.POINTER(Passwd),
        ctypes.c_char_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_int)
    ]
    err = ctypes.c_int()
    res = func(uid, result_p, buffer_p, buflen, ctypes.byref(err))

    return (int(res), err.value, result_p)


def __getpwent_r(result_p, buffer_p, buflen, nss_module):
    """
    enum nss_status _nss_#module#_getpwent_r(struct passwd *result,
                                             char *buffer, size_t buflen,
                                             int *errnop)
    """
    func = get_nss_func(NssOperation.GETPWENT, nss_module)
    func.restype = ctypes.c_int
    func.argtypes = [
        ctypes.POINTER(Passwd),
        ctypes.c_char_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_int)
    ]

    err = ctypes.c_int()
    res = func(result_p, buffer_p, buflen, ctypes.byref(err))

    return (int(res), err.value, result_p)


def __setpwent(nss_module):
    """
    enum nss_status _nss_#module#_setpwent(void)
    """
    func = get_nss_func(NssOperation.SETPWENT, nss_module)
    func.argtypes = []

    res = func()

    if res != NssReturnCode.SUCCESS:
        raise NssError(ctypes.get_errno(), NssOperation.SETPWENT, res, nss_module)


def __endpwent(nss_module):
    """
    enum nss_status _nss_#module#_endpwent(void)
    """
    func = get_nss_func(NssOperation.ENDPWENT, nss_module)
    func.argtypes = []

    res = func()

    if res != NssReturnCode.SUCCESS:
        raise NssError(ctypes.get_errno(), NssOperation.ENDPWENT, res, nss_module)


def __getpwent_impl(mod, as_dict, buffer_len=PASSWD_INIT_BUFLEN):
    result = Passwd()
    buf = ctypes.create_string_buffer(buffer_len)

    res, error, result_p = __getpwent_r(ctypes.byref(result), buf,
                                        buffer_len, mod)
    match error:
        case 0:
            pass
        case errno.ERANGE:
            # Our buffer was too small, increment
            return __getpwent_impl(mod, as_dict, buffer_len * 2)
        case _:
            raise NssError(error, NssOperation.GETPWENT, res, mod)

    if res != NssReturnCode.SUCCESS:
        return None

    return  __parse_nss_result(result, as_dict, mod.name)


def __getpwall_impl(module, as_dict):
    mod = NssModule[module]
    __setpwent(mod)
    pwd_list = []

    user = __getpwent_impl(mod, as_dict)
    while user is not None:
        if (user := __getpwent_impl(mod, as_dict)):
            pwd_list.append(user)

    __endpwent(mod)
    return pwd_list


def __getpwnam_impl(name, module, as_dict, buffer_len=PASSWD_INIT_BUFLEN):
    mod = NssModule[module]
    result = Passwd()
    buf = ctypes.create_string_buffer(buffer_len)

    res, error, result_p = __getpwnam_r(name, ctypes.byref(result),
                                        buf, buffer_len, mod)
    match error:
        case 0:
            pass
        case errno.ERANGE:
            # Our buffer was too small, increment
            return __getpwnam_impl(name, module, as_dict, buffer_len * 2)
        case _:
            raise NssError(error, NssOperation.GETPWNAM, res, mod)

    if res == NssReturnCode.NOTFOUND:
        return None

    return  __parse_nss_result(result, as_dict, mod.name)


def __getpwuid_impl(uid, module, as_dict, buffer_len=PASSWD_INIT_BUFLEN):
    mod = NssModule[module]
    result = Passwd()
    buf = ctypes.create_string_buffer(buffer_len)

    res, error, result_p = __getpwuid_r(uid, ctypes.byref(result),
                                        buf, buffer_len, mod)
    match error:
        case 0:
            pass
        case errno.ERANGE:
            # Our buffer was too small, increment
            return __getpwuid_impl(uid, module, as_dict, buffer_len * 2)
        case _:
            raise NssError(error, NssOperation.GETPWUID, res, mod)

    if res == NssReturnCode.NOTFOUND:
        return None

    return  __parse_nss_result(result, as_dict, mod.name)


def getpwuid(uid, module=NssModule.ALL.name, as_dict=False):
    """
    Return the password database entry for the given user by uid.

    `module` - NSS module from which to retrieve the user
    `as_dict` - return output as a dictionary rather than `struct_passwd`.
    """
    if module != NssModule.ALL.name:
        if (result := __getpwuid_impl(uid, module, as_dict)):
            return result

        raise KeyError(f"getpwuid(): uid not found: '{uid}'")

    # We're querying all modules
    for mod in NssModule:
        if mod == NssModule.ALL:
            continue

        try:
            if (result := __getpwuid_impl(uid, mod.name, as_dict)):
                return result
        except NssError as e:
            if e.return_code != NssReturnCode.UNAVAIL:
                raise e from None

    raise KeyError(f"getpwuid(): uid not found: '{uid}'")


def getpwnam(name, module=NssModule.ALL.name, as_dict=False):
    """
    Return the password database entry for the given user by name.

    `module` - NSS module from which to retrieve the user
    `as_dict` - return output as a dictionary rather than `struct_passwd`.
    """
    if module != NssModule.ALL.name:
        if (result := __getpwnam_impl(name, module, as_dict)):
            return result

        raise KeyError(f"getpwnam(): name not found: '{name}'")

    # We're querying all modules
    for mod in NssModule:
        if mod == NssModule.ALL:
            continue

        try:
            if (result := __getpwnam_impl(name, mod.name, as_dict)):
                return result
        except NssError as e:
            if e.return_code != NssReturnCode.UNAVAIL:
                raise e from None


    raise KeyError(f"getpwnam(): name not found: '{name}'")


def getpwall(module=NssModule.ALL.name, as_dict=False):
    """
    Returns all password entries on server (similar to pwd.getpwall()).

    `module` - NSS module from which to retrieve the entries
    `as_dict` - return password database entries as dictionaries

    This module returns a dictionary keyed by NSS module, e.g.
    {'FILES': [<struct_passwd>, <struct_passwd>], 'WINBIND': [], 'SSS': []}
    """
    if module != NssModule.ALL.name:
        return {module: __getpwall_impl(module, as_dict)}

    results = {}
    for mod in NssModule:
        if mod == NssModule.ALL:
            continue

        entries = []
        try:
            entries = __getpwall_impl(mod.name, as_dict)):
        except NssError as e:
            if e.return_code != NssReturnCode.UNAVAIL:
                raise e from None

        results[mod.name] = entries

    return results
