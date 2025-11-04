import errno

from middlewared.api import api_method
from middlewared.api.current import (
    WebshareShareEntry, SharingWebshareCreateArgs, SharingWebshareCreateResult,
    SharingWebshareUpdateArgs, SharingWebshareUpdateResult,
    SharingWebshareDeleteArgs, SharingWebshareDeleteResult,
)
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.service import private, SharingService
from middlewared.service import ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.path import FSLocation


class SharingWebshareModel(sa.Model):
    __tablename__ = 'sharing_webshare_share'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    path = sa.Column(sa.String(255))
    enabled = sa.Column(sa.Boolean())


class SharingWebshareService(SharingService):

    share_task_type = 'Webshare'
    allowed_path_types = [FSLocation.LOCAL]

    class Config:
        namespace = 'sharing.webshare'
        datastore = 'sharing.webshare_share'
        cli_namespace = 'sharing.webshare'
        role_prefix = 'SHARING_WEBSHARE'
        entry = WebshareShareEntry

    @api_method(
        SharingWebshareCreateArgs, SharingWebshareCreateResult,
        audit='Webshare share create',
        audit_extended=lambda data: data['name'],
    )
    async def do_create(self, data):
        verrors = ValidationErrors()

        await self.validate(data, 'sharing_webshare_create', verrors)

        verrors.check()

        compressed = await self.compress(data)
        data['id'] = await self.middleware.call('datastore.insert', self._config.datastore, compressed)

        await (await self.middleware.call('service.control', 'RELOAD', 'webshare')).wait(raise_error=True)

        await self.middleware.call('truesearch.configure')

        return await self.get_instance(data['id'])

    @api_method(
        SharingWebshareUpdateArgs, SharingWebshareUpdateResult,
        audit='Webshare share update',
        audit_callback=True,
    )
    async def do_update(self, audit_callback, id_, data):
        old = await self.get_instance(id_)
        audit_callback(old['name'])

        verrors = ValidationErrors()

        new = old.copy()
        new.update(data)

        await self.validate(new, 'sharing_webshare_update', verrors)

        verrors.check()

        compressed = await self.compress(new)
        await self.middleware.call('datastore.update', self._config.datastore, id_, compressed)

        await (await self.middleware.call('service.control', 'RELOAD', 'webshare')).wait(raise_error=True)

        await self.middleware.call('truesearch.configure')

        return await self.get_instance(id_)

    @api_method(
        SharingWebshareDeleteArgs, SharingWebshareDeleteResult,
        audit='Webshare share delete',
        audit_callback=True,
    )
    async def do_delete(self, audit_callback, id_):
        """
        Delete SMB Share of `id`. This will forcibly disconnect SMB clients
        that are accessing the share.
        """
        share = await self.get_instance(id_)
        audit_callback(share['name'])

        await self.middleware.call('datastore.delete', self._config.datastore, id_)

        await (await self.middleware.call('service.control', 'RELOAD', 'webshare')).wait(raise_error=True)

        await self.middleware.call('truesearch.configure')

    @private
    async def validate_share_name(self, name, schema_name, verrors, old=None):
        filters = [['name', 'C=', name]]
        if old:
            filters.append(['id', '!=', old['id']])

        if await self.query(filters, {'select': ['name']}):
            verrors.add(
                f'{schema_name}.name', 'Share with this name already exists.', errno.EEXIST
            )

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        await self.validate_share_name(data['name'], schema_name, verrors, old)

        await self.validate_path_field(data, schema_name, verrors)

    @private
    async def compress(self, data):
        data.pop(self.locked_field, None)

        return data


class WebshareFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'webshare'
    title = 'Webshare Share'
    service = 'webshare'
    service_class = SharingWebshareService

    async def restart_reload_services(self, attachments):
        await (await self.middleware.call('service.control', 'RELOAD', 'webshare')).wait(raise_error=True)

        await self.middleware.call('truesearch.configure')


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', WebshareFSAttachmentDelegate(middleware))
