import os
import threading

from middlewared.service_exception import CallError, MatchNotFound
from samba import param
from .constants import SMBPath
from .util_net_conf import reg_getparm

# This is safe to initialize because stub file never changes
LP_CTX = param.LoadParm(SMBPath.STUBCONF.platform())
LP_CTX_LOCK = threading.Lock()


def smbconf_getparm_file(param):
        with open(SMBPath.GLOBALCONF.platform(), "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.strip().startswith(("[", "#", ";")):
                    continue

                try:
                    k, v = line.split("=", 1)
                except ValueError:
                    continue

                k = k.strip()
                v = v.strip()

                if k.casefold() != param.casefold():
                    continue

                if v.lower() in ("off", "false", "no"):
                    return False

                if v.lower() in ("on", "true", "yes"):
                    return True

                if v.isnumeric():
                    return int(v)

                return v

        raise MatchNotFound(param)


def smbconf_getparm_lpctx(param):
    """
    This method uses our stub configuration to retrieve the samba
    default value for a parameter.
    """
    with LP_CTX_LOCK:
        return LP_CTX.get(param)


def smbconf_getparm(parm, section='GLOBAL'):
    """
    Some basic global configuration parameters (such as "clustering") are not stored in the
    registry. This means that we need to read them from the configuration file. This only
    applies to global section.

    Finally, we fall through to retrieving the default value in Samba's param table
    through samba's param binding. This is initialized under a non-default loadparm context
    based on empty smb4.conf file.
    """
    try:
        return reg_getparm(section, parm)
    except Exception as e:
        if not section.upper() == 'GLOBAL':
            raise CallError(f'Attempt to query smb4.conf parameter [{parm}] failed with error: {e}')

    if section.upper() == 'GLOBAL':
        try:
            return smbconf_getparm_file(parm)
        except MatchNotFound:
            pass

    return smbconf_getparm_lpctx(parm)


def lpctx_validate_global_parm(param):
    """
    lib/param doesn't validate params containing a colon.
    dump_a_parameter() wraps around the respective lp_ctx
    function in samba that checks the known parameter table.
    This should be a lightweight validation of GLOBAL params.
    """
    with LP_CTX_LOCK:
        LP_CTX.dump_a_parameter(param)
