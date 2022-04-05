import logging
import subprocess

from middlewared.schema import accepts, Dict, Str, ValidationErrors

from .base import Authenticator


logger = logging.getLogger(__name__)


class ShellAuthenticator(Authenticator):

    NAME = 'shell'
    PROPAGATION_DELAY = 60
    SCHEMA = Dict(
        'shell',
        Str('script', empty=False, null=True, title='Script'),
    )

    def initialize_credentials(self):
        self.script = self.attributes.get('script')

    @staticmethod
    @accepts(SCHEMA)
    def validate_credentials(data):
        pass

    def _perform(self, domain, validation_name, validation_content):
	    subprocess.run([self.script, "set", domain, validation_name, validation_content, "600"])

    def _cleanup(self, domain, validation_name, validation_content):
	    subprocess.run([self.script, "unset", domain, validation_name, validation_content])
