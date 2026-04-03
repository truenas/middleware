from __future__ import annotations

from acme import errors, messages
from cryptography import x509
from truenas_acme_utils.client_utils import ACMEClientAndKeyData, get_acme_client_and_key

from middlewared.service import ServiceContext
from middlewared.service_exception import CallError


def revoke_certificate(
    context: ServiceContext, acme_client_key_payload: ACMEClientAndKeyData, certificate: str,
) -> None:
    acme_client, key = get_acme_client_and_key(acme_client_key_payload)
    try:
        cert_obj = x509.load_pem_x509_certificate(certificate.encode())
        acme_client.revoke(cert_obj, 0)
    except (errors.ClientError, messages.Error) as e:
        raise CallError(f'Failed to revoke certificate: {e}')
