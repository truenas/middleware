import enum

from middlewared.api import api_method
from middlewared.api.current import (
    UpdateProfileChoicesArgs, UpdateProfileChoicesResult,
)
from middlewared.service import private, Service


class Profile(enum.IntEnum):
    DEVELOPER = 0
    TESTER = 1
    EARLY_ADOPTER = 2
    GENERAL = 3
    CONSERVATIVE = 4
    MISSION_CRITICAL = 5


class UpdateService(Service):

    @api_method(UpdateProfileChoicesArgs, UpdateProfileChoicesResult, roles=['SYSTEM_UPDATE_READ'])
    async def profile_choices(self):
        profiles = {}
        is_enterprise = await self.middleware.call('system.is_enterprise')
        current_profile = Profile[(await self.middleware.call('update.config'))['profile']]

        if not is_enterprise:
            profiles[Profile.DEVELOPER] = {
                'name': 'Developer',
                'footnote': '',
                'description': (
                    'Latest software with new features and bugs alike.  There is an opportunity to contribute '
                    'directly to the development process.'
                ),
            }
            profiles[Profile.TESTER] = {
                'name': 'Tester',
                'footnote': '',
                'description': (
                    'New software with recent features. Some bugs are expected and there is a willingness to provide '
                    'bug reports and feedback to the developers.'
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
            profiles[Profile.CONSERVATIVE] = {
                'name': 'Conservative',
                'footnote': '(Default)',
                'description': (
                    'Mature software with well documented limitations. Software updates are infrequent.'
                ),
            }
            profiles[Profile.MISSION_CRITICAL] = {
                'name': 'Mission Critical',
                'footnote': '(Default)',
                'description': (
                    'Mature software that enables 24×7 operations with high availability for a very clearly defined '
                    'use case. Software updates are very infrequent and based on need.'
                ),
            }

        for profile, data in profiles.items():
            data['available'] = True

        return {k.name: v for k, v in profiles.items()}

    @private
    async def profile_matches(self, name, selected_name):
        return Profile[name] >= Profile[selected_name]


async def post_license_update(middleware, prev_product_type, *args, **kwargs):
    if prev_product_type != 'ENTERPRISE' and await middleware.call('system.product_type') == 'ENTERPRISE':
        current_profile = Profile[(await middleware.call('update.config'))['profile']]
        if current_profile < Profile.CONSERVATIVE:
            await middleware.call('update.update', {'profile': Profile.CONSERVATIVE.name})


async def setup(middleware):
    middleware.register_hook('system.post_license_update', post_license_update)
