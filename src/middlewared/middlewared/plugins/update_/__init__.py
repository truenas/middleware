from __future__ import annotations

from typing import Literal, TYPE_CHECKING

from middlewared.api import api_method, Event
from middlewared.api.current import (
    UpdateAvailableVersion, UpdateAvailableVersionsArgs, UpdateAvailableVersionsResult,
    UpdateDownloadArgs, UpdateDownloadResult,
    UpdateConfigSafeEntry, UpdateEntry,
    UpdateFileArgs, UpdateFileOptions, UpdateFileResult,
    UpdateManualArgs, UpdateManualOptions, UpdateManualResult,
    UpdateProfileChoice, UpdateProfileChoicesArgs, UpdateProfileChoicesResult,
    UpdateRunArgs, UpdateRunAttrs, UpdateRunResult,
    UpdateStatus, UpdateStatusArgs, UpdateStatusResult, UpdateStatusChangedEvent,
    UpdateUpdate, UpdateUpdateArgs, UpdateUpdateResult,
)
from middlewared.service import ConfigService, job, private
from .config import UpdateConfigPart
from .download import download, get_update_location, verify_existing_update
from .profile_ import profile_choices, current_version_profile
from .status import status
from .update import run as update_run, manual as update_manual, file as update_file
from .version import available_versions


if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job
    from middlewared.main import Middleware

__all__ = ("UpdateService",)


class UpdateService(ConfigService[UpdateEntry]):
    class Config:
        cli_namespace = 'system.update'
        role_prefix = 'SYSTEM_UPDATE'
        entry = UpdateEntry
        events = [
            Event(
                name='update.status',
                description='Updated on update status changes.',
                roles=['SYSTEM_UPDATE_READ'],
                models={
                    'CHANGED': UpdateStatusChangedEvent,
                },
            ),
        ]
        generic = True

    def __init__(self, middleware: Middleware):
        super().__init__(middleware)
        self._update_config_part = UpdateConfigPart(self.context)

    async def config(self) -> UpdateEntry:
        return await self._update_config_part.config()

    @private
    async def config_safe(self) -> UpdateConfigSafeEntry:
        return await self._update_config_part.config_safe()

    @api_method(UpdateUpdateArgs, UpdateUpdateResult, check_annotations=True)
    async def do_update(self, data: UpdateUpdate) -> UpdateEntry:
        """
        Update update configuration.
        """
        return await self._update_config_part.do_update(data)

    @api_method(
        UpdateAvailableVersionsArgs,
        UpdateAvailableVersionsResult,
        roles=['SYSTEM_UPDATE_READ'],
        check_annotations=True,
    )
    async def available_versions(self) -> list[UpdateAvailableVersion]:
        """
        TrueNAS versions available for update.
        """
        return await available_versions(self.context)

    @api_method(
        UpdateProfileChoicesArgs,
        UpdateProfileChoicesResult,
        roles=['SYSTEM_UPDATE_READ'],
        check_annotations=True,
    )
    async def profile_choices(self) -> dict[str, UpdateProfileChoice]:
        """
        `profile` choices for configuration update.
        """
        return await profile_choices(self.context)

    @api_method(
        UpdateStatusArgs,
        UpdateStatusResult,
        roles=['SYSTEM_UPDATE_READ'],
        check_annotations=True,
    )
    async def status(self) -> UpdateStatus:
        """
        Update status.
        """
        return await status(self.context)

    @private
    async def set_profile(self, name: str) -> None:
        return await self._update_config_part.set_profile(name)

    @private
    async def current_version_profile(self) -> str:
        return await current_version_profile(self.context)

    @api_method(
        UpdateRunArgs,
        UpdateRunResult,
        roles=['SYSTEM_UPDATE_WRITE'],
        pass_app=True,
        check_annotations=True,
    )
    @job(lock='update')
    async def run(self, app: App, job: Job, attrs: UpdateRunAttrs) -> Literal[True]:
        """
        Downloads (if not already in cache) and apply an update.
        """
        return await update_run(self.context, app, job, attrs)

    @api_method(
        UpdateManualArgs,
        UpdateManualResult,
        roles=['SYSTEM_UPDATE_WRITE'],
        check_annotations=True,
    )
    @job(lock='update')
    def manual(self, job: Job, path: str, options: UpdateManualOptions) -> None:
        """
        Update the system using a manual update file.
        """
        return update_manual(self.context, job, path, options)

    @api_method(
        UpdateFileArgs,
        UpdateFileResult,
        roles=['SYSTEM_UPDATE_WRITE'],
        check_annotations=True,
    )
    @job(lock='update')
    async def file(self, job: Job, options: UpdateFileOptions) -> None:
        """
        Updates the system using the uploaded .tar file.
        """
        return await update_file(self.context, job, options)

    @api_method(UpdateDownloadArgs, UpdateDownloadResult, roles=['SYSTEM_UPDATE_WRITE'], check_annotations=True)
    @job()
    def download(self, job: Job, train: str | None, version: str | None) -> bool:
        """
        Download updates.
        """
        return download(self.context, job, train, version)

    @private
    def verify_existing_update(self) -> None:
        return verify_existing_update(self.context)

    @private
    def get_update_location(self) -> str:
        return get_update_location(self.context)
