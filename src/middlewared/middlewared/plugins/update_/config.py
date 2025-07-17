from middlewared.api import api_method
from middlewared.api.current import UpdateEntry, UpdateUpdateArgs, UpdateUpdateResult
from middlewared.service import ConfigService, private, ValidationErrors
import middlewared.sqlalchemy as sa

from .profile_ import Profile


class UpdateModel(sa.Model):
    __tablename__ = 'system_update'

    id = sa.Column(sa.Integer(), primary_key=True)
    upd_autocheck = sa.Column(sa.Boolean())
    upd_profile = sa.Column(sa.Text(), nullable=True)


class UpdateService(ConfigService):

    class Config:
        datastore = 'system.update'
        datastore_prefix = 'upd_'
        cli_namespace = 'system.update'
        role_prefix = 'SYSTEM_UPDATE'
        entry = UpdateEntry

    async def config(self):
        return await self.config_internal(allow_null_profile=False)

    @api_method(UpdateUpdateArgs, UpdateUpdateResult)
    async def do_update(self, data):
        """
        Update update configuration.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        profiles = await self.middleware.call('update.profile_choices')
        if (profile := profiles.get(new['profile'])) is None:
            verrors.add('update.profile', 'Invalid profile.')
        elif not profile['available']:
            verrors.add('update.profile', 'This profile is unavailable.')

        verrors.check()

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            old['id'],
            new,
            {'prefix': self._config.datastore_prefix},
        )

        if new['autocheck'] != old['autocheck']:
            await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        if new['profile'] != old['profile']:
            self.middleware.send_event('update.status', 'CHANGED', status=await self.middleware.call('update.status'))

        return await self.config()

    @private
    async def set_profile(self, name):
        # This must be used for setting update profile when internet connection might be unavailable.

        old = await self.config_internal()

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            old['id'],
            {'profile': Profile[name].name},
            {'prefix': self._config.datastore_prefix},
        )

    @private
    async def config_internal(self, *, allow_null_profile=True):
        data = await super().config()

        if data['profile'] is None and not allow_null_profile:
            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                data['id'],
                {'profile': await self.middleware.call('update.current_version_profile')},
                {'prefix': self._config.datastore_prefix},
            )
            return await super().config()

        return data


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'update', 'Update')
