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
import os
import pwd

from middlewared.schema import accepts, Dict, Str, Dir, File, Int, ValidationErrors
from middlewared.async_validators import check_path_resides_within_volume

from .base import Authenticator


logger = logging.getLogger(__name__)


class ShellAuthenticator(Authenticator):

    NAME = 'shell'
    PROPAGATION_DELAY = 60

    SCHEMA = Dict(
        'shell',
        File('script' , required=True, empty=False, title='Authenticator script'),
        Dir('workdir' , default='/tmp', title='Working directory'),
        Str('user'    , default='nobody', title='Running user'),
        Int('timeout' , default=60, title='Timeout'),
        Int('delay'   , default=60, title='Propagation delay'),
    )

    def initialize_credentials(self):
        self.script   = self.attributes.get('script')
        self.workdir  = self.attributes.get('workdir')
        self.user     = self.attributes.get('user')
        self.timeout  = int(self.attributes.get('timeout'))
        self.PROPAGATION_DELAY = int(self.attributes.get('delay'))

    @staticmethod
    @accepts(SCHEMA)
    def validate_credentials(data):
        pass

    def _run(self, args):
        def demote(uid, gid):
            def result():
                os.setgid(gid)
                os.setuid(uid)
            return result

        pw_record = pwd.getpwnam(self.user)
        env = os.environ.copy()
        env[ 'HOME'    ] = pw_record.pw_dir
        env[ 'LOGNAME' ] = pw_record.pw_name
        env[ 'PWD'     ] = self.workdir
        env[ 'USER'    ] = pw_record.pw_name
        process = subprocess.Popen(
            args, preexec_fn=demote(pw_record.pw_uid, pw_record.pw_gid), cwd=self.workdir, env=env
        )
        result = process.wait(timeout=self.timeout)
        return result

    def _perform(self, domain, validation_name, validation_content):
	    self._run([self.script, "set", domain, validation_name, validation_content, "600"])

    def _cleanup(self, domain, validation_name, validation_content):
	    self._run([self.script, "unset", domain, validation_name, validation_content])
