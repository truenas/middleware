from acme import errors, messages
from cryptography import x509
from truenas_acme_utils.client_utils import get_acme_client_and_key

from middlewared.service import CallError, Service


class ACMEService(Service):

    class Config:
        namespace = 'acme'
        private = True

    def revoke_certificate(self, acme_client_key_payload, certificate):
        acme_client, key = get_acme_client_and_key(acme_client_key_payload)
        try:
            cert_obj = x509.load_pem_x509_certificate(certificate.encode())
            acme_client.revoke(cert_obj, 0)
        except (errors.ClientError, messages.Error) as e:
            raise CallError(f'Failed to revoke certificate: {e}')
