import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    AppRegistryEntry, AppRegistryCreateArgs, AppRegistryCreateResult, AppRegistryUpdateArgs,
    AppRegistryUpdateResult, AppRegistryDeleteArgs, AppRegistryDeleteResult,
)
from middlewared.service import CRUDService, private, ValidationErrors

from .validate_registry import validate_registry_credentials


class AppRegistryModel(sa.Model):
    __tablename__ = 'app_registry'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.String(512), nullable=True, default=None)
    username = sa.Column(sa.EncryptedText(), nullable=False)
    password = sa.Column(sa.EncryptedText(), nullable=False)
    uri = sa.Column(sa.String(512), nullable=False, unique=True)


class AppRegistryService(CRUDService):

    class Config:
        namespace = 'app.registry'
        datastore = 'app.registry'
        cli_namespace = 'app.registry'
        entry = AppRegistryEntry
        role_prefix = 'APPS'

    @private
    async def validate(self, data, old=None, schema='app_registry_create'):
        verrors = ValidationErrors()

        filters = [['id', '!=', old['id']]] if old else []
        if await self.query([['name', '=', data['name']]] + filters):
            verrors.add(f'{schema}.name', 'Name must be unique')

        if data['uri'].startswith('http') and not data['uri'].endswith('/'):
            # We can have 2 formats basically
            # https://index.docker.io/v1/
            # registry-1.docker.io
            # We would like to have a trailing slash here because we are not able to pull images without it
            # if http based url is provided
            data['uri'] = data['uri'] + '/'

        if await self.query([['uri', '=', data['uri']]] + filters):
            verrors.add(f'{schema}.uri', 'URI must be unique')

        if not verrors and await self.middleware.run_in_thread(
            validate_registry_credentials, data['uri'], data['username'], data['password']
        ) is False:
            verrors.add(f'{schema}.uri', 'Invalid credentials for registry')

        verrors.check()

    @api_method(AppRegistryCreateArgs, AppRegistryCreateResult, roles=['APPS_WRITE'])
    async def do_create(self, data):
        """
        Create an app registry entry.
        """
        await self.middleware.call('docker.state.validate')
        await self.validate(data)
        id_ = await self.middleware.call('datastore.insert', 'app.registry', data)
        await self.middleware.call('etc.generate', 'app_registry')
        return await self.get_instance(id_)

    @api_method(AppRegistryUpdateArgs, AppRegistryUpdateResult, roles=['APPS_WRITE'])
    async def do_update(self, id_, data):
        """
        Update an app registry entry.
        """
        await self.middleware.call('docker.state.validate')
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        await self.validate(new, old=old, schema='app_registry_update')

        await self.middleware.call('datastore.update', 'app.registry', id_, new)

        await self.middleware.call('etc.generate', 'app_registry')
        return await self.get_instance(id_)

    @api_method(AppRegistryDeleteArgs, AppRegistryDeleteResult, roles=['APPS_WRITE'])
    async def do_delete(self, id_):
        """
        Delete an app registry entry.
        """
        await self.middleware.call('docker.state.validate')
        await self.get_instance(id_)
        await self.middleware.call('datastore.delete', 'app.registry', id_)
        await self.middleware.call('etc.generate', 'app_registry')
