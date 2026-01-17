from __future__ import annotations

import enum
import typing

from middlewared.api import api_method
from middlewared.api.current import (
    UpdateProfileChoice, UpdateProfileChoicesArgs, UpdateProfileChoicesResult,
)
from middlewared.service import private, Service
from middlewared.service_exception import CallError

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


class UpdateProfiles(enum.IntEnum):
    DEVELOPER = 0
    EARLY_ADOPTER = 1
    GENERAL = 2
    MISSION_CRITICAL = 3

    def describe(self, is_enterprise: bool, available: bool) -> UpdateProfileChoice:
        return {
            UpdateProfiles.DEVELOPER: UpdateProfileChoice(
                name='Developer',
                footnote='',
                description=(
                    'Developer software with new features and bugs alike. '
                    'Allows users to contribute directly to the development process.'
                ),
                available=available,
            ),
            UpdateProfiles.EARLY_ADOPTER: UpdateProfileChoice(
                name='Early Adopter',
                footnote='',
                description=(
                    'Pre-release access to new features and functionality of '
                    'TrueNAS software. Some issues may need workarounds, bug '
                    'reports or patience.'
                ),
                available=available,
            ),
            UpdateProfiles.GENERAL: UpdateProfileChoice(
                name='General',
                footnote='(not recommended)' if is_enterprise else '(Default)',
                description=(
                    'Field tested software with mature features. Few issues are expected.'
                ),
                available=available,
            ),
            UpdateProfiles.MISSION_CRITICAL: UpdateProfileChoice(
                name='Mission Critical',
                footnote='',
                description=(
                    'Mature software that enables 24×7 operations with high availability '
                    'for a very clearly defined use case. Software updates are very '
                    'infrequent and based on need.'
                ),
                available=available,
            )
        }.get(self, UpdateProfileChoice(name='', footnote='', description='', available=available))


class UpdateService(Service):

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
        profiles = {}
        config = await self.call2(self.s.update.config_internal)
        is_enterprise = await self.middleware.call('system.is_enterprise')
        current_profile = UpdateProfiles[await self.current_version_profile()]
        for profile in UpdateProfiles:
            available = profile.name == config.profile or profile <= current_profile
            info = profile.describe(is_enterprise, available)
            if is_enterprise:
                if profile >= UpdateProfiles.GENERAL:
                    profiles[profile.name] = info
            else:
                if profile <= UpdateProfiles.GENERAL:
                    profiles[profile.name] = info
        return profiles

    @private
    async def profile_matches(self, name: str, selected_name: str) -> bool:
        return UpdateProfiles[name] >= UpdateProfiles[selected_name]

    @private
    async def current_version_profile(self) -> str:
        manifest = await self.call2(self.s.update.get_manifest_file)
        current_train_releases = await self.call2(self.s.update.get_train_releases, manifest.train)
        current_version = await self.middleware.call('system.version_short')
        if (current_release := current_train_releases.get(current_version)) is None:
            if any(substring in current_version for substring in ('CUSTOM', 'INTERNAL', 'MASTER')):
                return 'DEVELOPER'

            raise CallError(
                f'Current software version ({current_version}) is not present in the update train releases file'
            )

        return current_release.profile


async def post_license_update(
    middleware: Middleware,
    prev_license: typing.Any,
    *args: typing.Any,
    **kwargs: typing.Any,
) -> None:
    if prev_license is None and await middleware.call('system.product_type') == 'ENTERPRISE':
        await middleware.call2(middleware.services.update.set_profile, UpdateProfiles.MISSION_CRITICAL.name)


async def setup(middleware: Middleware) -> None:
    middleware.register_hook('system.post_license_update', post_license_update)
