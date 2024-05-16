import asyncio
import socket

from middlewared.validators import IpAddress, check_path_resides_within_volume_sync


async def check_path_resides_within_volume(verrors, middleware, name, path):
    """
    async wrapper around synchronous general-purpose path validation function
    """
    vol_names = [vol["vol_name"] for vol in await middleware.call("datastore.query", "storage.volume")]
    return await middleware.run_in_thread(check_path_resides_within_volume_sync, verrors, name, path, vol_names)


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

    try:
        aw = middleware.create_task(middleware.run_in_thread(resolve_host_name_thread, hostname))
        result = await asyncio.wait_for(aw, timeout=5)
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


async def validate_port(middleware, schema, port, whitelist_namespace=None, bind_ip='0.0.0.0'):
    return await middleware.call('port.validate_port', schema, port, bind_ip, whitelist_namespace)
