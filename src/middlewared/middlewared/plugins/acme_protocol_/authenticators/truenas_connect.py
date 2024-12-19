import json
import logging
import requests

from middlewared.api.current import TrueNASConnectSchemaArgs
from middlewared.plugins.truenas_connect.mixin import auth_headers
from middlewared.plugins.truenas_connect.urls import LECA_DNS_URL
from middlewared.service import CallError

from .base import Authenticator


logger = logging.getLogger('truenas_connect')


class TrueNASConnectAuthenticator(Authenticator):

    NAME = 'tn_connect'
    PROPAGATION_DELAY = 20
    SCHEMA_MODEL = TrueNASConnectSchemaArgs
    INTERNAL = True

    @staticmethod
    async def validate_credentials(middleware, data):
        pass

    def _perform(self, domain, validation_name, validation_content):
        try:
            self._perform_internal(domain, validation_name, validation_content)
        except CallError:
            raise
        except Exception as e:
            raise CallError(f'Failed to perform {self.NAME} challenge for {domain!r} domain: {e}')

    def _perform_internal(self, domain, validation_name, validation_content):
        logger.debug(
            'Performing %r challenge for %r domain with %r validation name and %r validation content',
            self.NAME, domain, validation_name, validation_content,
        )
        response = requests.post(LECA_DNS_URL, data=json.dumps({
            'token': validation_content,
            'hostnames': [domain],  # We should be using validation name here
        }), headers=auth_headers(self.attributes))
        if response.status_code != 201:
            raise CallError(
                f'Failed to perform {self.NAME} challenge for {domain!r} domain with '
                f'{response.status_code!r} status code: {response.text}'
            )

        logger.debug('Successfully performed %r challenge for %r domain', self.NAME, domain)

    def _cleanup(self, domain, validation_name, validation_content):
        # We don't have any API in place to clean existing TXT records for TNC yet
        pass
