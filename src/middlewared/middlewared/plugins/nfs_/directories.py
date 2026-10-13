import errno
import os
import shutil

from middlewared.api.base import BaseModel
from middlewared.service import ServiceContext

from .status import clear_nfs3_rmtab
from .utils import NFSServicePathInfo

BuiltinName = int | str | None


class NFSNameToIdConversionArgs(BaseModel):
    name: BuiltinName
    name_type: str = "user"


class NFSNameToIdConversionResult(BaseModel):
    result: BuiltinName


class NFSSetupDirectoriesArgs(BaseModel):
    pass


class NFSSetupDirectoriesResult(BaseModel):
    result: None


def name_to_id_conversion(context: ServiceContext, name: BuiltinName, name_type: str = "user") -> BuiltinName:
    """Convert built-in user or group name to associated UID or GID"""
    if not isinstance(name, str):
        return name

    if name_type == "user":
        method = "user.get_builtin_user_id"
    elif name_type == "group":
        method = "group.get_builtin_group_id"
    else:
        context.logger.error("Unexpected name_type (%r)", name_type)
        return name

    try:
        resolved: BuiltinName = context.middleware.call_sync(method, name)
    except Exception as e:
        if getattr(e, "errno", None) == errno.ENOENT:
            context.logger.error("Failed to resolve builtin %s %r", name_type, name)
        else:
            context.logger.error("Unexpected error resolving builtin %s %r", name_type, name, exc_info=True)
        return name

    return resolved


def setup_directories(context: ServiceContext) -> None:
    """
    We are moving the NFS state directory from /var/lib/nfs to
    the system dataset: /var/db/system/nfs.
    When setup_directories is called /var/db/system/nfs is expected to exist.

    If STATEDIR is empty, then this might be an initialization
    and there might be current info in /var/lib/nfs.

    We always make sure the expected directories are present
    """
    state_dir = NFSServicePathInfo.STATEDIR.path
    try:
        shutil.copytree("/var/lib/nfs", state_dir)
    except FileExistsError:
        pass
    except Exception:
        context.logger.error("Unexpected error initializing %r", state_dir, exc_info=True)

    for entry in NFSServicePathInfo:
        uid = name_to_id_conversion(context, entry.uid, name_type="user")
        gid = name_to_id_conversion(context, entry.gid, name_type="group")
        if entry.is_dir:
            os.makedirs(entry.path, exist_ok=True)

        try:
            os.chmod(entry.path, entry.mode)
            if isinstance(uid, int) and isinstance(gid, int):
                os.chown(entry.path, uid, gid)
        except Exception:
            context.logger.error("Unexpected failure initializing %r", entry.path, exc_info=True)

    # Clear rmtab on boot.
    # We call this here because /var/db/system/nfs is not yet available
    # in a middleware 'setup' hook.  See NAS-131762
    if not context.middleware.call_sync("system.ready"):
        clear_nfs3_rmtab()
