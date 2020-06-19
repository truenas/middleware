import asyncio

from .base import SimpleService


class WebDAVService(SimpleService):
    name = "webdav"

    etc = ["webdav"]

    freebsd_rc = "apache24"
    freebsd_pidfile = "/var/run/httpd.pid"
    freebsd_procname = "httpd"

    systemd_unit = "apache2"

    async def after_stop(self):
        asyncio.ensure_future(self.middleware.call("sharing.webdav.remove_alerts_for_unlocked_datasets"))
