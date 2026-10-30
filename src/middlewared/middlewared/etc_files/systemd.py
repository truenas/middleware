import json

from truenas_os_pyutils.io import atomic_write
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.service.services.dbus_router import system_dbus


async def render(service, middleware):
    services_enabled = {}
    for service in await middleware.call("datastore.query", "services.services", [], {"prefix": "srv_"}):
        for unit in await middleware.call2(middleware.services.service.systemd_units, service["service"]):
            services_enabled[unit] = service["enable"]

    licensed = await middleware.call('failover.licensed')
    lio_enabled = await middleware.call('iscsi.global.lio_enabled')
    webshare_entitled = (
        await middleware.call2(middleware.services.truenas.entitlements.check, LicenseFeature.WEBSHARE)
    ).entitled

    for unit, enable in services_enabled.items():
        state = await system_dbus.get_unit_file_state(unit)
        if state not in ("enabled", "disabled"):
            middleware.logger.warning(
                "Unexpected unit file state %r for %s", state, unit
            )
            continue

        is_enabled = state == "enabled"
        if unit == "scst" and (licensed or lio_enabled):
            enable = False
        # strict: the unit state decides the next boot, where grace has ended
        if unit == 'truenas-webshare-auth':
            enable = enable and webshare_entitled

        if enable != is_enabled:
            await system_dbus.set_unit_file_state(unit, enable)

    # Write out a user enabled services to json file which shows which services user has enabled/disabled
    with atomic_write('/data/user-services.json', 'w', perms=0o600) as f:
        f.write(json.dumps(services_enabled))
