from __future__ import annotations

import os

from truenas_os_pyutils.truenas_shutil import CopyTreeConfig, copytree

from middlewared.service import ServiceContext

from .utils import get_netdata_state_path


def netdata_storage_location(context: ServiceContext) -> str | None:
    systemdataset_config = context.middleware.call_sync("systemdataset.config")
    if not systemdataset_config["path"]:
        return None

    return f"{systemdataset_config['path']}/netdata"


def netdata_state_location() -> str:
    # We don't check if system dataset is properly configured here because netdata conf won't be generated
    # if storage location is not properly configured which we check in the netdata etc file.
    return get_netdata_state_path()


def post_dataset_mount_action(context: ServiceContext) -> None:
    netdata_state_path = get_netdata_state_path()
    # We want to make sure this path exists always regardless of an error so that
    # at least netdata can start itself gracefully
    try:
        os.makedirs(netdata_state_path, exist_ok=False)
    except FileExistsError:
        return

    try:
        copytree("/var/lib/netdata", netdata_state_path, config=CopyTreeConfig())
    except Exception:
        context.logger.error("Failed to copy netdata state over from /var/lib/netdata", exc_info=True)
        os.chown(netdata_state_path, uid=999, gid=997)
        os.chmod(netdata_state_path, mode=0o755)


async def start_service(context: ServiceContext) -> None:
    if await context.middleware.call("failover.licensed"):
        return

    await (await context.middleware.call("service.control", "START", "netdata")).wait(raise_error=True)
