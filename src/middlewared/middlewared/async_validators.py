import asyncio
import os
import socket
from pathlib import Path

from middlewared.service import ValidationErrors
from middlewared.plugins.zfs_.utils import ZFSCTL
from middlewared.validators import IpAddress


async def check_path_resides_within_volume(verrors, middleware, name, path):

    # we need to make sure the sharing service is configured within the zpool
    def get_file_info(path):
        """
        avoid filesytem.stat here because we do not want to fail if path does
        not exist
        """
        rv = {'realpath': None, 'inode': None, 'dev': None, 'is_mountpoint': False}
        try:
            st = os.stat(path)
            rv['inode'] = st.st_ino
            rv['dev'] = st.st_dev
        except FileNotFoundError:
            pass

        rv['realpath'] = os.path.realpath(path)
        rv['is_mountpoint'] = os.path.ismount(path)
        return rv

    st = await middleware.run_in_thread(get_file_info, path)
    rp = st["realpath"]

    vol_names = [vol["vol_name"] for vol in await middleware.call("datastore.query", "storage.volume")]
    vol_paths = [os.path.join("/mnt", vol_name) for vol_name in vol_names]
    if not path.startswith("/mnt/") or not any(
        os.path.commonpath([parent]) == os.path.commonpath([parent, rp]) for parent in vol_paths
    ):
        verrors.add(name, "The path must reside within a pool mount point")

    if st['inode'] in (ZFSCTL.INO_ROOT, ZFSCTL.INO_SNAPDIR):
        verrors.add(name,
                    "The ZFS control directory (.zfs) and snapshot directory (.zfs/snapshot) "
                    "are not permitted paths. If a snapshot within this directory must "
                    "be accessed through the path-based API, then it should be called "
                    "directly, e.g. '/mnt/dozer/.zfs/snapshot/mysnap'.")

    # we must also make sure that any sharing service does not point to
    # anywhere within the ".glusterfs" dataset since the clients need
    # to go through the appropriate gluster client to write to the cluster.
    # If data is modified directly on the gluster resources, then it will
    # cause a split-brain scenario which means the data that was modified
    # would not be sync'ed with other nodes in the cluster.
    rp = Path(rp)
    for check_path, svc_name in (('.glusterfs', 'Gluster'), ('ix-applications', 'Applications')):
        in_use = False
        if st['is_mountpoint'] and rp.name == check_path:
            in_use = True
        else:
            # subtract 2 here to remove the '/' and 'mnt' parents
            for i in range(0, len(rp.parents) - 2):
                p = rp.parents[i]
                p_ismnt = await middleware.run_in_thread(p.is_mount)
                if p_ismnt and p.name == check_path:
                    in_use = True
                    break
        if in_use:
            verrors.add(name, f'A path being used by {svc_name} is not allowed')


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


async def validate_ports(middleware, schema, value):
    verrors = ValidationErrors()
    for port_attachment in await middleware.call('port.get_in_use'):
        if value in port_attachment['ports']:
            verrors.add(schema, f'The port is being used by {port_attachment["type"]!r}')

    return verrors
