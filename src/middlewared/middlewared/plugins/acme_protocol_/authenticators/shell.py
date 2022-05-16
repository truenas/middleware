"""
The authenticator script is called two times during the certificate generation:

1. The validation record creation which is called in the following way:
   script set domain validation_name validaton_context timeout
2. The validation record deletion which is called in following way:
   script unset domain validation_name validation_context

It is up to script implementation to handle both calls and perform the record creation.
"""
import logging
import subprocess

from middlewared.schema import accepts, Dict, Str, Dir, File, Int

from .base import Authenticator


logger = logging.getLogger(__name__)


class ShellAuthenticator(Authenticator):

    NAME = 'shell'
    PROPAGATION_DELAY = 60

    SCHEMA = Dict(
        'shell',
        File('script', required=True, empty=False, title='Authenticator script'),
        Str('user', default='nobody', title='Running user'),
        Int('timeout', default=60, title='Timeout'),
        Int('delay', default=60, title='Propagation delay'),
    )

    def initialize_credentials(self):
        self.script = self.attributes.get('script')
        self.user = self.attributes.get('user')
        self.timeout = int(self.attributes.get('timeout'))
        self.PROPAGATION_DELAY = int(self.attributes.get('delay'))

    @staticmethod
    @accepts(SCHEMA)
    def validate_credentials(data):
        # We would like to validate the following bits:
        # 1) script exists and is executable
        # 2) user exists
        # 3) User can access the script in question
        pass

    def _run(self, args):
        process = subprocess.Popen(
            ['sudo', '-H', '-u', self.user, 'sh', '-c', args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        try:
            process.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            process.kill()

    def _perform(self, domain, validation_name, validation_content):
        self._run([self.script, 'set', domain, validation_name, validation_content, '600'])

    def _cleanup(self, domain, validation_name, validation_content):
        self._run([self.script, 'unset', domain, validation_name, validation_content])
