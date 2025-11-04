import os

from middlewared.api import api_method
from middlewared.api.current import (
    WebshareServiceEntry, WebshareUpdateArgs, WebshareUpdateResult,
)
from middlewared.service import ConfigService, private
import middlewared.sqlalchemy as sa
from middlewared.utils.webshare import WEBSHARE_BULK_DOWNLOAD_PATH, WEBSHARE_DATA_PATH, WEBSHARE_UID, WEBSHARE_GID


class WebshareModel(sa.Model):
    __tablename__ = 'services_webshare'

    id = sa.Column(sa.Integer(), primary_key=True)
    search = sa.Column(sa.Boolean(), default=False)


class WebshareService(ConfigService):

    class Config:
        service = 'webshare'
        service_verb = 'reload'
        datastore = 'services.webshare'
        cli_namespace = 'service.webshare'
        role_prefix = 'SHARING_WEBSHARE'
        entry = WebshareServiceEntry

    @api_method(WebshareUpdateArgs, WebshareUpdateResult, audit='Update Webshare configuration')
    async def do_update(self, data):
        """
        Update Webshare Service Configuration.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        await self.middleware.call('datastore.update', self._config.datastore, new['id'], new)

        if old['search'] != new['search']:
            await self.middleware.call('truesearch.configure')

        await self._service_change(self._config.service, 'reload')

        return new

    @private
    def setup_directories(self):
        os.makedirs(WEBSHARE_BULK_DOWNLOAD_PATH, mode=0o700, exist_ok=False)
        os.chown(WEBSHARE_BULK_DOWNLOAD_PATH, WEBSHARE_UID, WEBSHARE_GID)

        os.makedirs(WEBSHARE_DATA_PATH, mode=0o700, exist_ok=False)
        os.chown(WEBSHARE_DATA_PATH, WEBSHARE_UID, WEBSHARE_GID)
