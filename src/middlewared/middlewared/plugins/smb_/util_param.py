import os
import threading

from middlewared.service_exception import CallError, MatchNotFound

try:
    from samba.samba3 import param
except ImportError:
    param = None

from .constants import SMBPath
from .util_net_conf import reg_getparm

LP_CTX = param.get_context()
LP_CTX_LOCK = threading.Lock()


def smbconf_getparm_lpctx(parm):
    with LP_CTX_LOCK:
        LP_CTX.load(SMBPath.GLOBALCONF.platform())
        return LP_CTX.get(parm)


def smbconf_getparm(parm, section='GLOBAL'):
    """
    The global SMB server settings can be retrieved using a samba3 loadparm
    context. This is required (as opposed to importing `param` from samba
    due to presence of registry shares.

    Share parameter must be queried directly from libsmbconf using `net conf`.
    """

    if section.upper() == 'GLOBAL':
        return smbconf_getparm_lpctx(parm)

    try:
        return reg_getparm(section, parm)
    except Exception as e:
        raise CallError(f'Attempt to query smb4.conf parameter [{parm}] failed with error: {e}')


def lpctx_validate_global_parm(parm):
    """
    lib/param doesn't validate params containing a colon.
    dump_a_parameter() wraps around the respective lp_ctx
    function in samba that checks the known parameter table.
    This should be a lightweight validation of GLOBAL params.
    """
    with LP_CTX_LOCK:
        LP_CTX.load(SMBPath.GLOBALCONF.platform())
        LP_CTX.dump_a_parameter(parm)
