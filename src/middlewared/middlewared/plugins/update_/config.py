from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import UpdateEntry, UpdateUpdate, UpdateUpdateArgs, UpdateUpdateResult
from middlewared.service import ConfigService, private, ValidationErrors
import middlewared.sqlalchemy as sa

from .download import UpdateService as DownloadUpdateService
from .install import UpdateService as InstallUpdateService
from .install_linux import UpdateService as InstallLinuxUpdateService
from .profile_ import UpdateProfiles, UpdateService as ProfileUpdateService
from .status import UpdateService as StatusUpdateService
from .trains import UpdateService as TrainsUpdateService
from .update import UpdateService as UpdateUpdateService
from .upload_location_linux import UpdateService as UploadLocationLinuxUpdateService
from .version import UpdateService as VersionUpdateService

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


class UpdateModel(sa.Model):  # type: ignore
    __tablename__ = 'system_update'

    id = sa.Column(sa.Integer(), primary_key=True)
    upd_autocheck = sa.Column(sa.Boolean())
    upd_profile = sa.Column(sa.Text(), nullable=True)


class UpdateService(DownloadUpdateService, InstallUpdateService, InstallLinuxUpdateService, ProfileUpdateService,
                    StatusUpdateService, TrainsUpdateService, UpdateUpdateService, UploadLocationLinuxUpdateService,
                    VersionUpdateService, ConfigService[UpdateEntry]):

    class Config:
        datastore = 'system.update'
        datastore_prefix = 'upd_'
        cli_namespace = 'system.update'
        role_prefix = 'SYSTEM_UPDATE'
        entry = UpdateEntry
        generic = True

    async def config(self) -> UpdateEntry:
        return await self.config_internal(allow_null_profile=False)

    @api_method(UpdateUpdateArgs, UpdateUpdateResult, check_annotations=True)
    async def do_update(self, data: UpdateUpdate) -> UpdateEntry:
        """
        Update update configuration.
        """
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
            self._config.datastore,
            old.id,
            new.model_dump(),
            {'prefix': self._config.datastore_prefix},
        )

        if new.autocheck != old.autocheck:
            await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        if new.profile != old.profile:
            self.middleware.send_event(
                'update.status', 'CHANGED', status=(await self.call2(self.s.update.status)).model_dump()
            )

            await self.middleware.call("alert.alert_source_clear_run", "HasUpdate")

        return await self.config()

    @private
    async def set_profile(self, name: str) -> None:
        # This must be used for setting update profile when internet connection might be unavailable.

        old = await self.config_internal()

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            old.id,
            {'profile': UpdateProfiles[name].name},
            {'prefix': self._config.datastore_prefix},
        )

    @private
    async def config_internal(self, *, allow_null_profile: bool = True) -> UpdateEntry:
        data = await super().config()

        if data.profile is None and not allow_null_profile:
            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                data.id,
                {'profile': await self.call2(self.s.update.current_version_profile)},
                {'prefix': self._config.datastore_prefix},
            )
            return await super().config()

        return data


async def setup(middleware: Middleware) -> None:
    await middleware.call('network.general.register_activity', 'update', 'Update')
