from __future__ import annotations

from typing import Any

from middlewared.api.current import WebshareEntry, WebshareUpdate
from middlewared.service import ConfigServicePart, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.webshare import WEBSHARE_GROUP

from .utils import bindip_choices as get_bindip_choices


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


class WebshareConfigPart(ConfigServicePart[WebshareEntry]):
    _datastore = 'services.webshare'
    _entry = WebshareEntry

    async def do_update(self, data: WebshareUpdate) -> WebshareEntry:
        old = await self.config()
        new = old.updated(data)
        verrors = ValidationErrors()

        await self._validate_bindip(new, verrors)
        login_groups = await self._resolve_login_groups(new, verrors)
        mcp_groups = await self._resolve_mcp_groups(new, login_groups, verrors)

        verrors.check()
        new.groups = [g['gr_name'] for g in login_groups]
        new.mcp_allowed_groups = [g['gr_name'] for g in mcp_groups]

        await self.middleware.call(
            'datastore.update', self._datastore, new.id, new.model_dump()
        )
        return new

    async def _validate_bindip(self, new: WebshareEntry, verrors: ValidationErrors) -> None:
        bindip_choices = await get_bindip_choices(self)
        for i, bindip in enumerate(new.bindip):
            if bindip not in bindip_choices:
                verrors.add(f'bindip.{i}', f'Cannot use {bindip}. Please provide a valid ip address.')

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
