import subprocess

import sqlite3

from middlewared.utils import osc


async def on_config_upload(middleware, path):
    await middleware.run_in_thread(on_config_upload_sync, middleware, path)


def on_config_upload_sync(middleware, path):
    if osc.IS_LINUX:
        # For SCALE, we have to enable/disable services based on the uploaded database
        enable_disable_units = {'enable': [], 'disable': []}
        conn = sqlite3.connect(path)
        try:
            cursor = conn.cursor()
            for service, enabled in cursor.execute(
                "SELECT srv_service, srv_enable FROM services_services"
            ).fetchall():
                try:
                    units = middleware.call_sync('service.systemd_units', service)
                except KeyError:
                    # An old service which we don't have currently
                    continue

                if enabled:
                    enable_disable_units['enable'].extend(units)
                else:
                    enable_disable_units['disable'].extend(units)
        finally:
            conn.close()

        for action in filter(lambda k: enable_disable_units[k], enable_disable_units):
            cp = subprocess.Popen(
                ['systemctl', action] + enable_disable_units[action],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            err = cp.communicate()[1]
            if cp.returncode:
                middleware.logger.error(
                    'Failed to %s %r systemctl units: %s', action,
                    ', '.join(enable_disable_units[action]), err.decode()
                )


async def setup(middleware):
    middleware.register_hook('config.on_upload', on_config_upload, sync=True)
