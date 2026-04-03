import json

from middlewared.plugins.service_.services.dbus_router import system_dbus
from truenas_os_pyutils.io import atomic_write


async def render(service, middleware):
    services_enabled = {}
    for service in await middleware.call("datastore.query", "services.services", [], {"prefix": "srv_"}):
        for unit in await middleware.call("service.systemd_units", service["service"]):
            services_enabled[unit] = service["enable"]

    licensed = await middleware.call('failover.licensed')

    # Services whose lifecycle is managed exclusively by middleware after
    # pool import. These depend on the system dataset (/var/db/system)
    # which is only available after middleware imports the pool and runs
    # systemdataset.setup(). Keeping them disabled in systemd prevents
    # noisy failures at boot when systemd tries to auto-start them before
    # the system dataset is mounted.
    middleware_managed_units = frozenset({'nfs-server'})

    for unit, enable in services_enabled.items():
        state = await system_dbus.get_unit_file_state(unit)
        if state not in ("enabled", "disabled"):
            middleware.logger.warning(
                "Unexpected unit file state %r for %s", state, unit
            )
            continue

        is_enabled = state == "enabled"
        if unit in middleware_managed_units:
            if is_enabled:
                await system_dbus.set_unit_file_state(unit, False)
            continue
        if unit == "scst" and licensed:
            enable = False

        if enable != is_enabled:
            await system_dbus.set_unit_file_state(unit, enable)

    # Write out a user enabled services to json file which shows which services user has enabled/disabled
    with atomic_write('/data/user-services.json', 'w', perms=0o600) as f:
        f.write(json.dumps(services_enabled))
