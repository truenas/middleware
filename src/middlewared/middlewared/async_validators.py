import asyncio
import os
import socket
from pathlib import Path

from middlewared.validators import IpAddress
from middlewared.utils import osc


async def check_path_resides_within_volume(verrors, middleware, name, path, gluster_bypass=False):

    # when a sharing service is using gluster, the path checks below do not apply
    if gluster_bypass:
        return

    # we need to make sure the sharing service is configured within the zpool
    rp = os.path.realpath(path)
    vol_names = [vol["vol_name"] for vol in await middleware.call("datastore.query", "storage.volume")]
    vol_paths = [os.path.join("/mnt", vol_name) for vol_name in vol_names]
    if not path.startswith("/mnt/") or not any(
        os.path.commonpath([parent]) == os.path.commonpath([parent, rp]) for parent in vol_paths
    ):
        verrors.add(name, "The path must reside within a pool mount point")

    if osc.IS_LINUX:
        # we must also make sure that any sharing service does not point to
        # anywhere within the ".glusterfs" dataset since the clients need
        # to go through the appropriate gluster client to write to the cluster.
        # If data is modified directly on the gluster resources, then it will
        # cause a split-brain scenario which means the data that was modified
        # would not be sync'ed with other nodes in the cluster.
        rp = Path(rp)

        using_gluster_path = False
        if rp.is_mount() and rp.name == '.glusterfs':
            using_gluster_path = True
        else:
            # subtract 2 here to remove the '/' and 'mnt' parents
            for i in range(0, len(rp.parents) - 2):
                if rp.parents[i].is_mount() and rp.parents[i].name == ".glusterfs":
                    using_gluster_path = True
                    break

        if using_gluster_path:
            verrors.add(name, "A path being used by Gluster is not allowed")


async def resolve_hostname(middleware, verrors, name, hostname):

    def resolve_host_name_thread(hostname):
        try:
            try:
                ip = IpAddress()
                ip(hostname)
                return hostname
            except ValueError:
                return socket.gethostbyname(hostname)
        except Exception:
            return False

    result_future = middleware.run_in_thread(resolve_host_name_thread, hostname)
    try:
        result = await asyncio.wait_for(result_future, 5, loop=asyncio.get_event_loop())
    except asyncio.futures.TimeoutError:
        result = False

    if not result:
        verrors.add(
            name,
            'Couldn\'t resolve hostname'
        )


async def validate_country(middleware, country_name, verrors, v_field_name):
    if country_name not in (await middleware.call('system.general.country_choices')):
        verrors.add(
            v_field_name,
            f'{country_name} not in countries recognized by the system'
        )
