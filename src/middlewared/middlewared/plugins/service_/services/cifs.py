from middlewared.service_exception import CallError

from .base import SimpleService, ServiceState

import os
import psutil
import signal
import time


class CIFSService(SimpleService):
    name = "cifs"
    reloadable = True

    etc = ["smb", "smb_share"]

    freebsd_rc = "smbd"
    freebsd_pidfile = "/var/run/samba4/smbd.pid"
    dcerpc_pidfile = "/var/run/samba4/samba-dcerpcd.pid"

    systemd_unit = "smbd"

    def lookup_pid(self):
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            if proc.info['name'] == 'samba-dcerpcd':
                return proc.info['pid']

        return None

    def get_pid(self):
        try:
            with open(self.dcerpc_pidfile, 'r') as f:
                return int(f.read().strip())
        except FileNotFoundError:
            return self.lookup_pid()
        except Exception:
            self.middleware.logger.debug('Failed to open pidfile', exc_info=True)

        return None

    def wait_on_pid(self, pid, timeout=10):
        while timeout > 0:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            except Exception:
                self.middleware.logger.warning('%s: liveness check failed', exc_info=True)
                break

            time.sleep(1)
            timeout -= 1

    def terminate_dcerpcd(self):
        pid = self.get_pid()
        if pid is None:
            return

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception:
            self.middleware.logger.warning('%d: failed to kill samba-dcerpcd', pid, exc_info=True)
            return

        self.wait_on_pid(pid)

        try:
            os.unlink(self.dcerpc_pidfile)
        except Exception:
            self.middleware.logger.warning('Failed to unlink dcerpcd pidfile', exc_info=True)

        self.middleware.logger.debug('Successfully shut down samba-dcerpcd')

    async def _get_state_freebsd(self):
        return ServiceState(
            (await self._freebsd_service("smbd", "status")).returncode == 0,
            [],
        )

    async def start(self):
        announce = (await self.middleware.call("network.configuration.config"))["service_announcement"]
        await self._freebsd_service("smbd", "start", force=True)
        await self._freebsd_service("winbindd", "start", force=True)
        if announce["netbios"]:
            await self._freebsd_service("nmbd", "start", force=True)
        if announce["wsd"]:
            await self.middleware.call('etc.generate', 'wsd')
            await self._freebsd_service("wsdd", "start", force=True)

    async def after_start(self):
        await self.middleware.call("service.reload", "mdns")

        try:
            await self.middleware.call("smb.add_admin_group", "", True)
        except Exception as e:
            raise CallError(e)

    async def stop(self):
        await self._freebsd_service("smbd", "stop", force=True)
        await self._freebsd_service("winbindd", "stop", force=True)
        await self._freebsd_service("nmbd", "stop", force=True)
        await self._freebsd_service("wsdd", "stop", force=True)
        await self.middleware.run_in_thread(self.terminate_dcerpcd)

    async def after_stop(self):
        await self.middleware.call("service.reload", "mdns")

    async def after_reload(self):
        await self.middleware.call("service.reload", "mdns")

    async def before_reload(self):
        await self.middleware.call("sharing.smb.sync_registry")
