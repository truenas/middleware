import json

from middlewared.plugins.service_.services.base import get_unit_file_state, set_unit_file_enabled
from middlewared.utils.io import atomic_write


async def render(service, middleware):
    services_enabled = {}
    for service in await middleware.call("datastore.query", "services.services", [], {"prefix": "srv_"}):
        for unit in await middleware.call("service.systemd_units", service["service"]):
            services_enabled[unit] = service["enable"]

    licensed = await middleware.call('failover.licensed')

    for unit, enable in services_enabled.items():
        state = await get_unit_file_state(unit)
        if state not in ("enabled", "disabled"):
            middleware.logger.warning(
                "Unexpected unit file state %r for %s", state, unit
            )
            continue

        is_enabled = state == "enabled"
        if unit == "scst" and licensed:
            enable = False

        if enable != is_enabled:
            await set_unit_file_enabled(unit, enable)

    # Write out a user enabled services to json file which shows which services user has enabled/disabled
    with atomic_write('/data/user-services.json', 'w', perms=0o600) as f:
        f.write(json.dumps(services_enabled))
