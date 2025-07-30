import enum

from middlewared.api import api_method
from middlewared.api.current import (
    UpdateProfileChoicesArgs, UpdateProfileChoicesResult,
)
from middlewared.service import private, Service
from middlewared.service_exception import CallError


class Profile(enum.IntEnum):
    DEVELOPER = 0
    EARLY_ADOPTER = 1
    GENERAL = 2
    MISSION_CRITICAL = 3


class UpdateService(Service):

    @api_method(UpdateProfileChoicesArgs, UpdateProfileChoicesResult, roles=['SYSTEM_UPDATE_READ'])
    async def profile_choices(self):
        """
        `profile` choices for configuration update.
        """
        profiles = {}
        is_enterprise = await self.middleware.call('system.is_enterprise')

        if not is_enterprise:
            profiles[Profile.DEVELOPER] = {
                'name': 'Developer',
                'footnote': '',
                'description': (
                    'Latest software with new features and bugs alike.  There is an opportunity to contribute '
                    'directly to the development process.'
                ),
            }
            profiles[Profile.EARLY_ADOPTER] = {
                'name': 'Early Adopter',
                'footnote': '',
                'description': (
                    'Released software with new features. Data is protected, but some issues may need workarounds or '
                    'patience.'
                ),
            }
            profiles[Profile.GENERAL] = {
                'name': 'General',
                'footnote': '(Default)',
                'description': (
                    'Field tested software with mature features. Few issues are expected.'
                ),
            }
        else:
            profiles[Profile.GENERAL] = {
                'name': 'General',
                'footnote': '(not recommended)',
                'description': (
                    'Field tested software with mature features. Few issues are expected.'
                ),
            }
            profiles[Profile.MISSION_CRITICAL] = {
                'name': 'Mission Critical',
                'footnote': '',
                'description': (
                    'Mature software that enables 24×7 operations with high availability for a very clearly defined '
                    'use case. Software updates are very infrequent and based on need.'
                ),
            }

        current_profile = Profile[await self.current_version_profile()]
        for profile, data in profiles.items():
            data['available'] = profile <= current_profile

        return {k.name: v for k, v in profiles.items()}

    @private
    async def profile_matches(self, name, selected_name):
        return Profile[name] >= Profile[selected_name]

    @private
    async def current_version_profile(self, trains=None):
        if trains is None:
            trains = await self.middleware.call('update.get_trains')

        current_train_name = await self.middleware.call('update.get_current_train_name', trains)
        current_train_releases = await self.middleware.call('update.get_train_releases', current_train_name)
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
        current_profile = Profile[(await middleware.call('update.config'))['profile']]
        if current_profile < Profile.MISSION_CRITICAL:
            await middleware.call('update.set_profile', Profile.MISSION_CRITICAL.name)


async def setup(middleware):
    middleware.register_hook('system.post_license_update', post_license_update)
