import os
import threading

from middlewared.service_exception import CallError, MatchNotFound
from samba import param
from .constants import SMBPath
from .util_net_conf import reg_getparm

LP_CTX_LOCK = threading.Lock()


def smbconf_getparm_lpctx(param):
    """
    This method uses our stub configuration to retrieve the samba
    default value for a parameter.
    """
    with LP_CTX_LOCK:
        ctx = param.LoadParm(SMBPath.GLOBALCONF.platform())
        return ctx.get(param)


def smbconf_getparm(parm, section='GLOBAL'):
    """
    Some basic global configuration parameters (such as "clustering") are not stored in the
    registry. This means that we need to read them from the configuration file. This only
    applies to global section.

    Finally, we fall through to retrieving the default value in Samba's param table
    through samba's param binding. This is initialized under a non-default loadparm context
    based on empty smb4.conf file.
    """

    if section.upper() == 'GLOBAL':
        return smbconf_getparm_file(parm)

    try:
        return reg_getparm(section, parm)
    except Exception as e:
        raise CallError(f'Attempt to query smb4.conf parameter [{parm}] failed with error: {e}')


def lpctx_validate_global_parm(param):
    """
    lib/param doesn't validate params containing a colon.
    dump_a_parameter() wraps around the respective lp_ctx
    function in samba that checks the known parameter table.
    This should be a lightweight validation of GLOBAL params.
    """
    with LP_CTX_LOCK:
        ctx = param.LoadParm(SMBPath.GLOBALCONF.platform())
        LP_CTX.dump_a_parameter(param)
