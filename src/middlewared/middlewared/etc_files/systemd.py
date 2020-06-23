import json
import re

from middlewared.service import CallError
from middlewared.utils import run

RE_IS_NOT_A_NATIVE_SERVICE = re.compile(r"(.+)\.service is not a native service, redirecting to systemd-sysv-install\.")


async def render(service, middleware):
    services = []
    services_enabled = {}
    for service in await middleware.call("datastore.query", "services.services", [], {"prefix": "srv_"}):
        for unit in await middleware.call("service.systemd_units", service["service"]):
            services.append(unit)
            services_enabled[unit] = service["enable"]

    p = await run(["systemctl", "is-enabled"] + services, check=False, encoding="utf-8", errors="ignore")
    are_enabled = p.stdout.strip().split()
    if len(are_enabled) != len(services):
        raise CallError(p.stderr.strip())

    # sysv inits are handled first by systemd
    # https://github.com/systemd/systemd/blob/161bc1b62777b3f32ce645a8e128007a654a2300/src/systemctl/systemctl.c#L7093
    services_native = []
    for line in p.stderr.splitlines():
        if m := RE_IS_NOT_A_NATIVE_SERVICE.match(line):
            service = m.group(1)
            services.remove(service)
            services_native.append(service)
    services = services_native + services

    for service, is_enabled in zip(services, are_enabled):
        enable = services_enabled[service]
        is_enabled = {"enabled": True, "disabled": False}[is_enabled]
        if enable != is_enabled:
            await run(["systemctl", "enable" if enable else "disable", service])

    # Write out a user enabled services to json file which shows which services user has enabled/disabled
    with open('/data/user-services.json', 'w') as f:
        f.write(json.dumps(services_enabled))
