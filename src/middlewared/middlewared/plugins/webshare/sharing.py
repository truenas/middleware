from __future__ import annotations

import errno
from typing import Any, TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    SharingWebshareEntry, SharingWebshareCreate, SharingWebshareCreateArgs, SharingWebshareCreateResult,
    SharingWebshareUpdate, SharingWebshareUpdateArgs, SharingWebshareUpdateResult,
    SharingWebshareDeleteArgs, SharingWebshareDeleteResult,
)
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.service import private, SharingService
from middlewared.service import ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.path import FSLocation
from middlewared.utils.types import AuditCallback

if TYPE_CHECKING:
    from middlewared.main import Middleware


class SharingWebshareModel(sa.Model):
    __tablename__ = 'sharing_webshare_share'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    path = sa.Column(sa.String(255))
    dataset = sa.Column(sa.String(255), nullable=True)
    relative_path = sa.Column(sa.String(255), nullable=True)
    is_home_base = sa.Column(sa.Boolean())
    enabled = sa.Column(sa.Boolean())


class SharingWebshareService(SharingService[SharingWebshareEntry]):

    share_task_type = 'Webshare'
    allowed_path_types = [FSLocation.LOCAL]

    class Config:
        namespace = 'sharing.webshare'
        datastore = 'sharing.webshare_share'
        cli_namespace = 'sharing.webshare'
        role_prefix = 'SHARING_WEBSHARE'
        generic = True
        entry = SharingWebshareEntry

    @api_method(
        SharingWebshareCreateArgs, SharingWebshareCreateResult,
        audit='Webshare share create',
        audit_extended=lambda data: data['name'],
        check_annotations=True,
    )
    async def do_create(self, data: SharingWebshareCreate) -> SharingWebshareEntry:
        verrors = ValidationErrors()

        await self.validate(data, 'sharing_webshare_create', verrors)

        verrors.check()

        id_ = await self.middleware.call('datastore.insert', self._config.datastore, self.compress(data))

        await (await self.middleware.call('service.control', 'RELOAD', 'webshare')).wait(raise_error=True)

        await self.call2(self.s.truesearch.configure)

        return await self.get_instance(id_)

    @api_method(
        SharingWebshareUpdateArgs, SharingWebshareUpdateResult,
        audit='Webshare share update',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(
        self,
        audit_callback: AuditCallback,
        id_: int,
        data: SharingWebshareUpdate,
    ) -> SharingWebshareEntry:
        old = await self.get_instance(id_)
        audit_callback(old.name)

        verrors = ValidationErrors()

        new = old.updated(data)

        await self.validate(new, 'sharing_webshare_update', verrors, old)

        verrors.check()

        await self.middleware.call('datastore.update', self._config.datastore, id_, self.compress(new))

        await (await self.middleware.call('service.control', 'RELOAD', 'webshare')).wait(raise_error=True)

        await self.call2(self.s.truesearch.configure)

        return await self.get_instance(id_)

    @api_method(
        SharingWebshareDeleteArgs, SharingWebshareDeleteResult,
        audit='Webshare share delete',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> None:
        """
        Delete SMB Share of `id`. This will forcibly disconnect SMB clients
        that are accessing the share.
        """
        share = await self.get_instance(id_)
        audit_callback(share.name)

        await self.middleware.call('datastore.delete', self._config.datastore, id_)

        await (await self.middleware.call('service.control', 'RELOAD', 'webshare')).wait(raise_error=True)

        await self.call2(self.s.truesearch.configure)

    @private
    async def validate_share_name(
        self,
        name: str,
        schema_name: str,
        verrors: ValidationErrors,
        old: SharingWebshareEntry | None = None,
    ) -> None:
        filters: list[list[int | str]] = [['name', 'C=', name]]
        if old:
            filters.append(['id', '!=', old.id])

        if await self.query(filters, {'select': ['name']}):
            verrors.add(
                f'{schema_name}.name', 'Share with this name already exists.', errno.EEXIST
            )

    @private
    async def validate(
        self,
        data: SharingWebshareEntry,
        schema_name: str,
        verrors: ValidationErrors,
        old: SharingWebshareEntry | None = None,
    ) -> None:
        await self.validate_share_name(data.name, schema_name, verrors, old)

        await self.validate_path_field(data, schema_name, verrors, split_path=True)

        if data.is_home_base:
            filters = [['is_home_base', '=', True]]
            if old:
                filters.append(['id', '!=', old.id])

            if await self.query(filters, {'select': ['id']}):
                verrors.add(
                    f'{schema_name}.is_home_base',
                    'Only one share can be configured as home directory base.',
                    errno.EEXIST
                )

    @private
    def compress(self, data: SharingWebshareEntry) -> dict[str, Any]:
        compressed = data.model_dump()
        compressed.pop(self.locked_field, None)
        return compressed


class WebshareFSAttachmentDelegate(LockableFSAttachmentDelegate[SharingWebshareEntry]):
    name = 'webshare'
    title = 'Webshare Share'
    service = 'webshare'
    service_class = SharingWebshareService

    async def restart_reload_services(self, attachments: list[SharingWebshareEntry]) -> None:
        await (await self.middleware.call('service.control', 'RELOAD', 'webshare')).wait(raise_error=True)

        await self.call2(self.s.truesearch.configure)


async def setup(middleware: Middleware) -> None:
    await middleware.call(
        'pool.dataset.register_attachment_delegate',
        WebshareFSAttachmentDelegate(middleware),  # type: ignore[no-untyped-call]
    )
