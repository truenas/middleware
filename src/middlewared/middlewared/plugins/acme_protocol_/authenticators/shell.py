"""
The authenticator script is called two times during the certificate generation:

1. The validation record creation which is called in the following way:
   script set domain validation_name validaton_context timeout
2. The validation record deletion which is called in following way:
   script unset domain validation_name validation_context

It is up to script implementation to handle both calls and perform the record creation.
"""
import logging

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.schema import accepts, Dict, Str, File, Int
from middlewared.service import CallError, skip_arg, ValidationErrors
from middlewared.utils.osc.linux.user_context import run_command_with_user_context

from .base import Authenticator


logger = logging.getLogger(__name__)


class ShellAuthenticator(Authenticator):

    NAME = 'shell'
    PROPAGATION_DELAY = 60

    SCHEMA = Dict(
        'shell',
        File('script', required=True, empty=False, title='Authenticator script'),
        Str('user', default='nobody', title='Running user', empty=False),
        Int('timeout', default=60, title='Timeout'),
        Int('delay', default=60, title='Propagation delay'),
    )

    def initialize_credentials(self):
        self.script = self.attributes['script']
        self.user = self.attributes['user']
        self.timeout = self.attributes['timeout']
        self.PROPAGATION_DELAY = self.attributes['delay']

    @staticmethod
    @accepts(SCHEMA)
    @skip_arg(count=1)
    async def validate_credentials(middleware, data):
        # We would like to validate the following bits:
        # 1) script exists and is executable
        # 2) user exists
        # 3) User can access the script in question
        verrors = ValidationErrors()
        try:
            await middleware.call('user.get_user_obj', {'username': data['user']})
        except KeyError:
            verrors.add('user', f'Unable to locate {data["user"]!r} user')

        await check_path_resides_within_volume(verrors, middleware, 'script', data['script'])

        try:
            can_access = await middleware.call(
                'filesystem.can_access_as_user', data['user'], data['script'], {'execute': True}
            )
        except CallError as e:
            verrors.add('script', f'Unable to validate script: {e}')
        else:
            if not can_access:
                verrors.add('user', f'{data["user"]!r} user does not has permission to execute the script')

        verrors.check()

    def _perform(self, domain, validation_name, validation_content):
        run_command_with_user_context(
            f'{self.script} set {domain} {validation_name} {validation_content}', self.user,
            disable_output=True, timeout=self.timeout
        )

    def _cleanup(self, domain, validation_name, validation_content):
        run_command_with_user_context(
            f'{self.script} unset {domain} {validation_name} {validation_content}', self.user,
            disable_output=True, timeout=self.timeout
        )
