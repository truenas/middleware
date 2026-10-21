from __future__ import annotations

import sqlite3
import subprocess
from typing import TYPE_CHECKING

from middlewared.service_exception import MatchNotFound

if TYPE_CHECKING:
    from middlewared.main import Middleware


def on_config_upload(middleware: Middleware, path: str) -> None:
    # For SCALE, we have to enable/disable services based on the uploaded database
    enable_disable_units: dict[str, list[str]] = {'enable': [], 'disable': []}
    conn = sqlite3.connect(path)
    try:
        cursor = conn.cursor()
        for service, enabled in cursor.execute('SELECT srv_service, srv_enable FROM services_services').fetchall():
            try:
                units = middleware.call_sync2(middleware.services.service.systemd_units, service)
            except MatchNotFound:
                # An old service which we don't have currently
                continue

            if enabled:
                enable_disable_units['enable'].extend(units)
            else:
                enable_disable_units['disable'].extend(units)
    finally:
        conn.close()

    need_enabled = []
    need_disabled = []
    for action, services in enable_disable_units.items():
        cp = subprocess.run(['systemctl', 'is-enabled'] + services, stdout=subprocess.PIPE, encoding='utf8',
                            errors='ignore')
        for service, line in zip(services, cp.stdout.split('\n')):
            if (line := line.strip()):
                if line == 'disabled' and action == 'enable':
                    need_enabled.append(service)
                elif line == 'enabled' and action == 'disable':
                    need_disabled.append(service)

    if need_enabled:
        cp = subprocess.run(
            ['systemctl', 'enable'] + need_enabled, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf8',
            errors='ignore',
        )
        if cp.returncode:
            middleware.logger.error(
                'Failed to enable systemd units %r with error %r',
                ', '.join(need_enabled), cp.stdout,
            )

    if need_disabled:
        cp = subprocess.run(
            ['systemctl', 'disable'] + need_disabled, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf8',
            errors='ignore',
        )
        if cp.returncode:
            middleware.logger.error(
                'Failed to disable systemd units %r with error %r',
                ', '.join(need_enabled), cp.stdout,
            )


async def setup(middleware: Middleware) -> None:
    middleware.register_hook('config.on_upload', on_config_upload, sync=True)
