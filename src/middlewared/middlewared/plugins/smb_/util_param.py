import errno
import threading

from middlewared.service_exception import CallError

try:
    from samba import param
except ImportError:
    param = None

from .constants import SMBPath

LP_CTX_LOCK = threading.Lock()

AUX_PARAM_BLACKLIST = frozenset([
    'state directory',
    'private directory',
    'lock directory',
    'lock dir',
    'config backend',
    'private dir',
    'log level',
    'cache directory',
    'clustering',
    'ctdb socket',
    'socket options',
    'include',
    'wide links',
    'insecure wide links',
    'zfs_core:zfs_block_cloning',
    'zfs_core:zfs_integrity_streams',
    'use sendfile',
    'vfs objects',
])


def smbconf_getparm_lpctx(parm, section):
    with LP_CTX_LOCK:
        LP_CTX = param.LoadParm(SMBPath.GLOBALCONF.platform())
        shares = set([s.casefold() for s in LP_CTX.services()])
        if section.upper() != 'GLOBAL' and section.casefold() not in shares:
            raise CallError(f'{section}: share does not exist in running configuration', errno.ENOENT)

        return LP_CTX.get(parm, section)


def smbconf_list_shares() -> list[str]:
    with LP_CTX_LOCK:
        LP_CTX = param.LoadParm(SMBPath.GLOBALCONF.platform())
        return LP_CTX.services()


def smbconf_getparm(parm, section='GLOBAL'):
    return smbconf_getparm_lpctx(parm, section)


def lpctx_validate_parm(parm, value, section):
    """
    Validate a given parameter using a temporary loadparm context from
    a stub smb.conf file

    WARNING: lib/param doesn't validate params containing a colon
    """
    with LP_CTX_LOCK:
        testconf = param.LoadParm(SMBPath.STUBCONF.platform())
        if section == 'GLOBAL':
            # Using param.set allows validation of parameter contents
            # which helps avoid certain types of foot-shooting
            testconf.set(parm, value)
        else:
            # We're limited by python param here and so we can check
            # that the parameter at least exists, but not its value.
            # Going to beyond this is probably not worth effort.
            testconf.dump_a_parameter(value, section)


def smbconf_sanity_check() -> None:
    """
    If user has done something phenomenally ill-advised with the
    SMB configuration then this will raise a ValidationError
    """

    with LP_CTX_LOCK:
        param.LoadParm(SMBPath.GLOBALCONF.platform())
