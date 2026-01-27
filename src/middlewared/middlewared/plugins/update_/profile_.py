from __future__ import annotations

import enum
import typing

from middlewared.api.current import UpdateProfileChoice
from middlewared.service import ServiceContext
from middlewared.service_exception import CallError
from .trains import get_manifest_file, get_train_releases

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


async def profile_choices(context: ServiceContext) -> dict[str, UpdateProfileChoice]:
    profiles = {}
    config = await context.call2(context.s.update.config_safe)
    is_enterprise = await context.middleware.call('system.is_enterprise')
    current_profile = UpdateProfiles[await current_version_profile(context)]
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


async def profile_matches(context: ServiceContext, name: str, selected_name: str) -> bool:
    return UpdateProfiles[name] >= UpdateProfiles[selected_name]


async def current_version_profile(context: ServiceContext) -> str:
    manifest = get_manifest_file()
    current_train_releases = await get_train_releases(context, manifest.train)
    current_version = await context.middleware.call('system.version_short')
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
