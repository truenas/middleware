import enum

from middlewared.api import api_method
from middlewared.api.current import (
    UpdateProfileChoicesArgs, UpdateProfileChoicesResult,
)
from middlewared.service import private, Service
from middlewared.service_exception import CallError


class UpdateProfiles(enum.IntEnum):
    DEVELOPER = 0
    EARLY_ADOPTER = 1
    GENERAL = 2
    MISSION_CRITICAL = 3

    def describe(self, is_enterprise=False):
        return {
            UpdateProfiles.DEVELOPER: {
                'name': 'Developer',
                'footnote': '',
                'description': (
                    'Developer software with new features and bugs alike. '
                    'Allows users to contribute directly to the development process.'
                ),
            },
            UpdateProfiles.EARLY_ADOPTER: {
                'name': 'Early Adopter',
                'footnote': '',
                'description': (
                    'Pre-release access to new features and functionality of '
                    'TrueNAS software. Some issues may need workarounds, bug '
                    'reports or patience.'
                ),
            },
            UpdateProfiles.GENERAL: {
                'name': 'General',
                'footnote': '(not recommended)' if is_enterprise else '(Default)',
                'description': (
                    'Field tested software with mature features. Few issues are expected.'
                ),
            },
            UpdateProfiles.MISSION_CRITICAL: {
                'name': 'Mission Critical',
                'footnote': '',
                'description': (
                    'Mature software that enables 24×7 operations with high availability '
                    'for a very clearly defined use case. Software updates are very '
                    'infrequent and based on need.'
                )
            }
        }.get(self, {'name': '', 'footnote': '', 'description': ''})


class UpdateService(Service):

    @api_method(UpdateProfileChoicesArgs, UpdateProfileChoicesResult, roles=['SYSTEM_UPDATE_READ'])
    async def profile_choices(self):
        """
        `profile` choices for configuration update.
        """
        profiles = {}
        is_enterprise = await self.middleware.call('system.is_enterprise')
        current_profile = UpdateProfiles[await self.current_version_profile()]
        for profile in UpdateProfiles:
            info = profile.describe(is_enterprise) | {'available': profile <= current_profile}
            if is_enterprise:
                if profile >= UpdateProfiles.GENERAL:
                    profiles[profile.name] = info
            else:
                profiles[profile.name] = info
        return profiles

    @private
    async def profile_matches(self, name, selected_name):
        return UpdateProfiles[name] >= UpdateProfiles[selected_name]

    @private
    async def current_version_profile(self):
        manifest = await self.middleware.call('update.get_manifest_file')
        current_train_releases = await self.middleware.call('update.get_train_releases', manifest['train'])
        current_version = await self.middleware.call('system.version_short')
        if (current_release := current_train_releases.get(current_version)) is None:
            if any(substring in current_version for substring in ('CUSTOM', 'INTERNAL', 'MASTER')):
                return 'DEVELOPER'

            raise CallError(
                f'Current software version ({current_version}) is not present in the update train releases file'
            )

        return current_release['profile']


async def post_license_update(middleware, prev_license, *args, **kwargs):
    if prev_license is None and await middleware.call('system.product_type') == 'ENTERPRISE':
        current_profile = UpdateProfiles[(await middleware.call('update.config'))['profile']]
        if current_profile < UpdateProfiles.MISSION_CRITICAL:
            await middleware.call('update.set_profile', UpdateProfiles.MISSION_CRITICAL.name)


async def setup(middleware):
    middleware.register_hook('system.post_license_update', post_license_update)
