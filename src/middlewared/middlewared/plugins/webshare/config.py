from __future__ import annotations

import os
from typing import Any, TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    WebshareEntry, WebshareUpdate, WebshareUpdateArgs, WebshareUpdateResult,
    WebshareBindipChoicesArgs, WebshareBindipChoicesResult,
)
from middlewared.service import ConfigService, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.webshare import WEBSHARE_BULK_DOWNLOAD_PATH, WEBSHARE_DATA_PATH, WEBSHARE_GROUP

if TYPE_CHECKING:
    from middlewared.main import Middleware


class WebshareModel(sa.Model):
    __tablename__ = 'services_webshare'

    id = sa.Column(sa.Integer(), primary_key=True)
    bindip = sa.Column(sa.JSON(list), default=[])
    search = sa.Column(sa.Boolean(), default=False)
    passkey = sa.Column(sa.String(20), default='DISABLED')
    groups = sa.Column(sa.JSON(list), default=[])
    mcp_enabled = sa.Column(sa.Boolean(), default=False)
    mcp_allowed_groups = sa.Column(sa.JSON(list), default=[])
    mcp_allow_write = sa.Column(sa.Boolean(), default=False)


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

        verrors = ValidationErrors()

        await self._validate_bindip(new, verrors)
        await self._validate_search(new, verrors)
        login_groups = await self._resolve_login_groups(new, verrors)
        mcp_groups = await self._resolve_mcp_groups(new, login_groups, verrors)

        verrors.check()
        new.groups = [g['gr_name'] for g in login_groups]
        new.mcp_allowed_groups = [g['gr_name'] for g in mcp_groups]

        await self.middleware.call('datastore.update', self._config.datastore, new.id, new.model_dump())

        if old.search != new.search:
            await self.call2(self.s.truesearch.configure)

        await self._service_change(self._config.service, 'reload')

        return new

    async def _validate_bindip(self, new: WebshareEntry, verrors: ValidationErrors) -> None:
        bindip_choices = await self.bindip_choices()
        for i, bindip in enumerate(new.bindip):
            if bindip not in bindip_choices:
                verrors.add(f'bindip.{i}', f'Cannot use {bindip}. Please provide a valid ip address.')

    async def _validate_search(self, new: WebshareEntry, verrors: ValidationErrors) -> None:
        if not new.search:
            return

        if reasons := await self.call2(self.s.truesearch.unavailable_reasons):
            verrors.add('search', 'Share indexing service is not available. ' + ' '.join(reasons))

    async def _resolve_login_groups(self, new: WebshareEntry, verrors: ValidationErrors) -> list[dict[str, Any]]:
        if not new.groups:
            return []

        if not (await self.middleware.call('system.general.config'))['ds_auth']:
            verrors.add('groups', 'Directory Service authentication is disabled.')
            return []

        groups: list[dict[str, Any]] = []
        for i, group in enumerate(new.groups):
            try:
                group_obj = await self.middleware.call('group.get_group_obj', {'groupname': group})
            except KeyError:
                verrors.add(f'groups.{i}', f'{group}: group does not exist.')
                continue

            if group_obj['local']:
                verrors.add(f'groups.{i}', f'{group}: group must be a Directory Service group.')
                continue

            groups.append(group_obj)

        return groups

    async def _resolve_mcp_groups(
        self, new: WebshareEntry, login_groups: list[dict[str, Any]], verrors: ValidationErrors,
    ) -> list[dict[str, Any]]:
        if new.mcp_enabled and not new.mcp_allowed_groups:
            verrors.add('mcp_allowed_groups', 'At least one group is required to enable MCP.')

        if not new.mcp_allowed_groups:
            return []

        webshare_group = await self.middleware.call('group.get_group_obj', {'groupname': WEBSHARE_GROUP})
        allowed_gids = {webshare_group['gr_gid']} | {g['gr_gid'] for g in login_groups}

        groups: list[dict[str, Any]] = []
        for i, group in enumerate(new.mcp_allowed_groups):
            try:
                group_obj = await self.middleware.call('group.get_group_obj', {'groupname': group})
            except KeyError:
                verrors.add(f'mcp_allowed_groups.{i}', f'{group}: group does not exist.')
                continue

            # Webshare checks login groups only at consent, so this keeps MCP access from outliving Webshare access.
            if group_obj['gr_gid'] not in allowed_gids:
                verrors.add(
                    f'mcp_allowed_groups.{i}',
                    f'{group}: group must also grant Webshare access ({WEBSHARE_GROUP} or a group in groups).',
                )
                continue

            groups.append(group_obj)

        return groups

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
        hostnames = await self.middleware.call("tn_connect.hostname.details")
        return [f"https://{hostname}:755" for hostname in sorted(hostnames)]


async def tn_connect_hostname_updated(middleware: Middleware) -> None:
    if not await middleware.call("service.started", "webshare"):
        return

    await middleware.call("service.control", "RELOAD", "webshare")


async def setup(middleware: Middleware) -> None:
    middleware.register_hook("tn_connect.hostname.updated", tn_connect_hostname_updated)
