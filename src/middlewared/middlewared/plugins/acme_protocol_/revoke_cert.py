from OpenSSL import crypto

import josepy as jose
from acme import errors, messages

from middlewared.service import CallError, Service

from .client_utils import get_acme_client_and_key


class ACMEService(Service):

    class Config:
        namespace = 'acme'
        private = True

    def revoke_certificate(self, acme_client_key_payload, certificate):
        acme_client, key = get_acme_client_and_key(acme_client_key_payload)
        try:
            acme_client.revoke(
                jose.ComparableX509(crypto.load_certificate(crypto.FILETYPE_PEM, certificate)), 0
            )
        except (errors.ClientError, messages.Error) as e:
            raise CallError(f'Failed to revoke certificate: {e}')
