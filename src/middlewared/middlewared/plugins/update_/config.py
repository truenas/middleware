from __future__ import annotations

import typing

from middlewared.api.current import UpdateConfigSafeEntry, UpdateEntry, UpdateUpdate
from middlewared.service import ConfigServicePart, ValidationErrors
import middlewared.sqlalchemy as sa
from .profile_ import UpdateProfiles, current_version_profile


if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


class UpdateModel(sa.Model):
    __tablename__ = 'system_update'

    id = sa.Column(sa.Integer(), primary_key=True)
    upd_autocheck = sa.Column(sa.Boolean())
    upd_profile = sa.Column(sa.Text(), nullable=True)


class UpdateConfigPart(ConfigServicePart[UpdateEntry]):
    _datastore = 'system_update'
    _datastore_prefix = 'upd_'
    _entry = UpdateEntry
    _default_entry = UpdateConfigSafeEntry

    async def config(self) -> UpdateEntry:
        return await self.config_internal(allow_null_profile=False)  # type: ignore

    async def config_safe(self) -> UpdateConfigSafeEntry:
        return await self.config_internal(allow_null_profile=True)

    async def config_internal(self, *, allow_null_profile: bool) -> UpdateConfigSafeEntry:
        data = await super().config()

        if data.profile is None and not allow_null_profile:
            await self.middleware.call(
                'datastore.update',
                self._datastore,
                data.id,
                {'profile': await current_version_profile(self)},
                {'prefix': self._datastore_prefix},
            )
            return await super().config()

        return data

    async def do_update(self, data: UpdateUpdate) -> UpdateEntry:
        old = await self.config()

        new = old.updated(data)

        verrors = ValidationErrors()
        profiles = await self.call2(self.s.update.profile_choices)
        if (profile := profiles.get(new.profile)) is None:
            verrors.add('update.profile', 'Invalid profile.')
        elif not profile.available:
            verrors.add('update.profile', 'This profile is unavailable.')

        verrors.check()

        await self.middleware.call(
            'datastore.update',
            self._datastore,
            old.id,
            new.model_dump(),
            {'prefix': self._datastore_prefix},
        )

        if new.autocheck != old.autocheck:
            await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        if new.profile != old.profile:
            self.middleware.send_event(
                'update.status', 'CHANGED', status=(await self.call2(self.s.update.status)).model_dump()
            )

            await self.middleware.call("alert.alert_source_clear_run", "HasUpdate")

        return await self.config()

    async def set_profile(self, name: str) -> None:
        # This must be used for setting update profile when internet connection might be unavailable.

        old = await self.config_safe()

        await self.middleware.call(
            'datastore.update',
            self._datastore,
            old.id,
            {'profile': UpdateProfiles[name].name},
            {'prefix': self._datastore_prefix},
        )


async def setup(middleware: Middleware) -> None:
    await middleware.call('network.general.register_activity', 'update', 'Update')
