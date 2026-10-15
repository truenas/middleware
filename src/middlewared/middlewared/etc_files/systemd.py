import json

from truenas_os_pyutils.io import atomic_write
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.service.services.dbus_router import system_dbus
from middlewared.plugins.service.services.webshare import unit_file_enabled


async def render(service, middleware):
    webshare_entitled = (
        await middleware.call2(middleware.services.truenas.entitlements.check, LicenseFeature.WEBSHARE)
    ).entitled
    services_enabled = {}
    units_enabled = {}
    for service in await middleware.call("datastore.query", "services.services", [], {"prefix": "srv_"}):
        unit_enable = unit_file_enabled(service["service"], service["enable"], webshare_entitled)
        for unit in await middleware.call2(middleware.services.service.systemd_units, service["service"]):
            services_enabled[unit] = service["enable"]
            units_enabled[unit] = unit_enable

    licensed = await middleware.call('failover.licensed')
    lio_enabled = await middleware.call('iscsi.global.lio_enabled')

    for unit, enable in units_enabled.items():
        state = await system_dbus.get_unit_file_state(unit)
        if state not in ("enabled", "disabled"):
            middleware.logger.warning(
                "Unexpected unit file state %r for %s", state, unit
            )
            continue

        is_enabled = state == "enabled"
        if unit == "scst" and (licensed or lio_enabled):
            enable = False

        if enable != is_enabled:
            await system_dbus.set_unit_file_state(unit, enable)

    # Write out a user enabled services to json file which shows which services user has enabled/disabled
    with atomic_write('/data/user-services.json', 'w', perms=0o600) as f:
        f.write(json.dumps(services_enabled))
