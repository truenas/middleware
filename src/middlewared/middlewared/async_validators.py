import asyncio
import os
import socket


from middlewared.validators import IpAddress


async def check_path_resides_within_volume(verrors, middleware, name, path):
    rp = os.path.realpath(path)
    vol_names = [vol["vol_name"] for vol in await middleware.call("datastore.query", "storage.volume")]
    vol_paths = [os.path.join("/mnt", vol_name) for vol_name in vol_names]
    if not path.startswith("/mnt/") or not any(
            os.path.commonpath([parent]) == os.path.commonpath([parent, rp]) for parent in vol_paths
    ):
        verrors.add(name, "The path must reside within a volume mount point")


async def resolve_hostname(middleware, verrors, name, hostname):

    def resolve_host_name_thread(hostname):
        try:
            try:
                ip = IpAddress()
                ip(hostname)
                return hostname
            except ValueError:
                # gethostbyadd() is called here so that if a short-hand IP
                # was provided (i.e. 192.168), gethostaddr() will raise the
                # exception as intended. The getaddrinfo() will auto-expand
                # short-hand IP addresses which isn't desired.
                socket.gethostbyaddr(hostname)
                result = socket.getaddrinfo(hostname, None flags=socket.AI_CANONNAME)
                return result[0][3] # canonical name
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
            f'Unable to resolve {hostname} or invalid IP address'
        )


async def validate_country(middleware, country_name, verrors, v_field_name):
    if country_name not in (await middleware.call('system.general.country_choices')):
        verrors.add(
            v_field_name,
            f'{country_name} not in countries recognized by the system'
        )
