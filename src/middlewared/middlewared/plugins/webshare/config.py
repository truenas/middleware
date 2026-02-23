from __future__ import annotations

import os
from typing import Any, TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    WebshareEntry, WebshareUpdate, WebshareUpdateArgs, WebshareUpdateResult,
    WebshareBindipChoicesArgs, WebshareBindipChoicesResult,
)
from middlewared.service import ConfigService, private, ValidationError
import middlewared.sqlalchemy as sa
from middlewared.utils.webshare import WEBSHARE_BULK_DOWNLOAD_PATH, WEBSHARE_DATA_PATH

if TYPE_CHECKING:
    from middlewared.main import Middleware

HOSTNAMES_KEY = "webshare_hostnames"


class WebshareModel(sa.Model):
    __tablename__ = 'services_webshare'

    id = sa.Column(sa.Integer(), primary_key=True)
    bindip = sa.Column(sa.JSON(list), default=[])
    search = sa.Column(sa.Boolean(), default=False)
    passkey = sa.Column(sa.String(20), default='DISABLED')
    groups = sa.Column(sa.JSON(list), default=[])


class WebshareService(ConfigService[WebshareEntry]):

    class Config:
        service = 'webshare'
        service_verb = 'reload'
        datastore = 'services.webshare'
        cli_namespace = 'service.webshare'
        role_prefix = 'SHARING_WEBSHARE'
        generic = True
        entry = WebshareEntry

    @api_method(WebshareUpdateArgs, WebshareUpdateResult, audit='Update Webshare configuration', check_annotations=True)
    async def do_update(self, data: WebshareUpdate) -> WebshareEntry:
        """
        Update Webshare Service Configuration.
        """
        old = await self.config()
        new = old.updated(data)

        bindip_choices = await self.bindip_choices()
        for i, bindip in enumerate(new.bindip):
            if bindip not in bindip_choices:
                raise ValidationError(f'bindip.{i}', f'Cannot use {bindip}. Please provide a valid ip address.')

        if new.groups:
            if not (await self.middleware.call('system.general.config'))['ds_auth']:
                raise ValidationError('groups', 'Directory Service authentication is disabled.')
            else:
                for i, group in enumerate(new.groups):
                    try:
                        group_obj = await self.middleware.call('group.get_group_obj', {'groupname': group})
                    except KeyError:
                        raise ValidationError(f'groups.{i}', f'{group}: group does not exist.')
                    else:
                        if group_obj['local']:
                            raise ValidationError(f'groups.{i}', f'{group}: group must be an Directory Service group.')

        await self.middleware.call('datastore.update', self._config.datastore, new.id, new.model_dump())

        if old.search != new.search:
            await self.call2(self.s.truesearch.configure)

        await self._service_change(self._config.service, 'reload')

        return new

    @api_method(WebshareBindipChoicesArgs, WebshareBindipChoicesResult, check_annotations=True)
    async def bindip_choices(self) -> dict[str, str]:
        """
        Returns ip choices for NFS service to use
        """
        return {
            d['address']: d['address']
            for d in await self.middleware.call('interface.ip_in_use', {'static': True})
        }

    @private
    def setup_directories(self) -> None:
        os.makedirs(WEBSHARE_BULK_DOWNLOAD_PATH, mode=0o700, exist_ok=True)

        os.makedirs(WEBSHARE_DATA_PATH, mode=0o700, exist_ok=True)

    @private
    async def urls(self) -> list[str]:
        try:
            hostnames = await self.call2(self.s.keyvalue.get, HOSTNAMES_KEY)
        except KeyError:
            hostnames = hostnames_from_config(await self.middleware.call("tn_connect.hostname.config"))

        return [f"https://{hostname}:755" for hostname in hostnames]


def hostnames_from_config(tn_connect_hostname_config: dict[str, Any]) -> list[str]:
    return sorted(list(tn_connect_hostname_config["hostname_details"].keys()))


async def tn_connect_hostname_updated(middleware: Middleware, tn_connect_hostname_config: dict[str, Any]) -> None:
    hostnames = hostnames_from_config(tn_connect_hostname_config)
    await middleware.call2(middleware.services.keyvalue.set, HOSTNAMES_KEY, hostnames)
    if not await middleware.call("service.started", "webshare"):
        # We do not want to reload webshare if it's not running
        # but we still however do want the hostnames key to be set
        return

    await middleware.call("service.control", "RELOAD", "webshare")


async def setup(middleware: Middleware) -> None:
    middleware.register_hook("tn_connect.hostname.updated", tn_connect_hostname_updated)
