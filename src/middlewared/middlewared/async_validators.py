import asyncio
import os
import socket


async def check_path_resides_within_volume(verrors, middleware, name, path):
    vol_names = [vol["vol_name"] for vol in await middleware.call("datastore.query", "storage.volume")]
    vol_paths = [os.path.join("/mnt", vol_name) for vol_name in vol_names]
    if not any(os.path.commonpath([parent]) == os.path.commonpath([parent, path]) for parent in vol_paths):
        verrors.add(name, "The path must reside within a volume mount point")


async def resolve_hostname(middleware, verrors, name, hostname):

    def resolve_host_name_thread(hostname):
        try:
            return socket.gethostbyname(hostname)
        except Exception:
            return False

    result_future = middleware.run_in_io_thread(resolve_host_name_thread, hostname)
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
