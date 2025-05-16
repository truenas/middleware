from middlewared.api import api_method
from middlewared.api.current import UpdateEntry, UpdateUpdateArgs, UpdateUpdateResult
from middlewared.service import ConfigService, ValidationErrors
import middlewared.sqlalchemy as sa


class UpdateModel(sa.Model):
    __tablename__ = 'system_update'

    id = sa.Column(sa.Integer(), primary_key=True)
    upd_autocheck = sa.Column(sa.Boolean())
    upd_profile = sa.Column(sa.Text())


class UpdateService(ConfigService):

    class Config:
        datastore = 'system.update'
        datastore_prefix = 'upd_'
        cli_namespace = 'system.update'
        role_prefix = 'SYSTEM_UPDATE'
        entry = UpdateEntry

    @api_method(UpdateUpdateArgs, UpdateUpdateResult)
    async def do_update(self, data):
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

        await self.middleware.call('datastore.update', 'system.update', old['id'], new, {'prefix': 'upd_'})

        if new['autocheck'] != old['autocheck']:
            await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        return await self.config()


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'update', 'Update')
