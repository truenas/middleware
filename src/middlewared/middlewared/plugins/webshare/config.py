import os

from middlewared.api import api_method
from middlewared.api.current import (
    WebshareEntry, WebshareUpdate, WebshareUpdateArgs, WebshareUpdateResult,
)
from middlewared.service import ConfigService, private
import middlewared.sqlalchemy as sa
from middlewared.utils.webshare import WEBSHARE_BULK_DOWNLOAD_PATH, WEBSHARE_DATA_PATH

HOSTNAMES_KEY = "webshare_hostnames"


class WebshareModel(sa.Model):
    __tablename__ = 'services_webshare'

    id = sa.Column(sa.Integer(), primary_key=True)
    search = sa.Column(sa.Boolean(), default=False)
    passkey = sa.Column(sa.String(20), default='DISABLED')


class WebshareService(ConfigService):

    class Config:
        service = 'webshare'
        service_verb = 'reload'
        datastore = 'services.webshare'
        cli_namespace = 'service.webshare'
        role_prefix = 'SHARING_WEBSHARE'
        entry = WebshareEntry

    @api_method(WebshareUpdateArgs, WebshareUpdateResult, audit='Update Webshare configuration', check_annotations=True)
    async def do_update(self, data: WebshareUpdate) -> WebshareEntry:
        """
        Update Webshare Service Configuration.
        """
        old = WebshareEntry(**await self.config())
        new = old.updated(data)

        await self.middleware.call('datastore.update', self._config.datastore, new.id, new.model_dump())

        if old.search != new.search:
            await self.middleware.call('truesearch.configure')

        await self._service_change(self._config.service, 'reload')

        return new

    @private
    def setup_directories(self):
        os.makedirs(WEBSHARE_BULK_DOWNLOAD_PATH, mode=0o700, exist_ok=True)

        os.makedirs(WEBSHARE_DATA_PATH, mode=0o700, exist_ok=True)

    @private
    async def urls(self):
        try:
            hostnames = await self.call2(self.s.keyvalue.get, HOSTNAMES_KEY)
        except KeyError:
            hostnames = hostnames_from_config(await self.middleware.call("tn_connect.hostname.config"))

        return [f"https://{hostname}:755" for hostname in hostnames]


def hostnames_from_config(tn_connect_hostname_config):
    return sorted(list(tn_connect_hostname_config["hostname_details"].keys()))


async def tn_connect_hostname_updated(middleware, tn_connect_hostname_config):
    hostnames = hostnames_from_config(tn_connect_hostname_config)
    await middleware.call2(middleware.services.keyvalue.set, HOSTNAMES_KEY, hostnames)
    if not await middleware.call("service.started", "webshare"):
        # We do not want to reload webshare if it's not running
        # but we still however do want the hostnames key to be set
        return

    await middleware.call("service.control", "RELOAD", "webshare")


async def setup(middleware):
    middleware.register_hook("tn_connect.hostname.updated", tn_connect_hostname_updated)
