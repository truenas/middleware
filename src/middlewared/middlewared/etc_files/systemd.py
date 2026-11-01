import json

from truenas_os_pyutils.io import atomic_write

from middlewared.plugins.service.services.dbus_router import system_dbus


async def render(service, middleware):
    services_enabled = {}
    for service in await middleware.call("datastore.query", "services.services", [], {"prefix": "srv_"}):
        enable = service["enable"]
        if enable:
            obj = await middleware.call2(middleware.services.service.object, service["service"])
            try:
                enable = await obj.may_enable_at_boot()
            except Exception:
                middleware.logger.error(
                    "%s: unable to decide whether to enable at boot; leaving it disabled",
                    service["service"],
                    exc_info=True,
                )
                enable = False

        for unit in await middleware.call2(middleware.services.service.systemd_units, service["service"]):
            services_enabled[unit] = enable

    licensed = await middleware.call('failover.licensed')
    lio_enabled = await middleware.call('iscsi.global.lio_enabled')

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

        if enable != is_enabled:
            await system_dbus.set_unit_file_state(unit, enable)

    # The boot decision rather than srv_enable: an upgrade enables these units in the new boot environment before
    # middleware can veto them.
    with atomic_write('/data/user-services.json', 'w', perms=0o600) as f:
        f.write(json.dumps(services_enabled))
