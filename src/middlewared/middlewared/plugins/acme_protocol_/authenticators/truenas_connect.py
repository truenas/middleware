import json
import logging
import requests

from truenas_connect_utils.urls import get_leca_cleanup_url, get_leca_dns_url

from middlewared.api.current import TrueNASConnectSchemaArgs
from middlewared.plugins.truenas_connect.mixin import auth_headers
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
        tnc_config = self.middleware.call_sync('tn_connect.config_internal')
        try:
            response = requests.post(get_leca_dns_url(tnc_config), data=json.dumps({
                'token': validation_content,
                'hostnames': [domain],  # We should be using validation name here
            }), headers=auth_headers(self.attributes), timeout=30)
        except requests.Timeout:
            raise CallError(f'Timeout while performing {self.NAME} challenge for {domain!r} domain')

        if response.status_code != 201:
            raise CallError(
                f'Failed to perform {self.NAME} challenge for {domain!r} domain with '
                f'{response.status_code!r} status code: {response.text}'
            )

        logger.debug('Successfully performed %r challenge for %r domain', self.NAME, domain)

    def _cleanup(self, domain, validation_name, validation_content):
        logger.debug('Cleaning up %r challenge for %r domain', self.NAME, domain)
        tnc_config = self.middleware.call_sync('tn_connect.config_internal')
        try:
            requests.delete(
                get_leca_cleanup_url(tnc_config), headers=auth_headers(self.attributes), timeout=30, data=json.dumps({
                    'hostnames': [validation_name],  # We use validation name here instead of domain as Zack advised
                })
            )
        except Exception:
            # We do not make this fatal as it does not matter if we fail to clean-up
            logger.debug('Failed to cleanup %r challenge for %r domain', self.NAME, domain, exc_info=True)
