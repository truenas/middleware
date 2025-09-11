import asyncio
import ipaddress
import socket

from middlewared.validators import check_path_resides_within_volume_sync


async def check_path_resides_within_volume(verrors, middleware, schema_name, path, must_be_dir=False):
    """
    async wrapper around synchronous general-purpose path validation function
    """
    vol_names = [vol["vol_name"] for vol in await middleware.call("datastore.query", "storage.volume")]
    return await middleware.run_in_thread(
        check_path_resides_within_volume_sync,
        verrors, schema_name, path, vol_names, must_be_dir
    )


async def resolve_hostname(middleware, verrors, name, hostname):

    def resolve_host_name_thread(hostname):
        try:
            try:
                ipaddress.ip_address(hostname)
                return hostname
            except ValueError:
                return socket.gethostbyname(hostname)
        except Exception:
            return False

    try:
        aw = middleware.create_task(middleware.run_in_thread(resolve_host_name_thread, hostname))
        result = await asyncio.wait_for(aw, timeout=5)
    except TimeoutError:
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
