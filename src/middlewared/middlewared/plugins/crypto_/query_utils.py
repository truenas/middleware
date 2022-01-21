import os

from .utils import (
    CA_TYPE_EXISTING, CA_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE, CERT_TYPE_EXISTING, CERT_TYPE_INTERNAL,
    CERT_TYPE_CSR, CERT_ROOT_PATH, CERT_CA_ROOT_PATH,
)


def normalize_cert_attrs(cert: dict) -> None:
    # Remove ACME related keys if cert is not an ACME based cert
    if not cert.get('acme'):
        for key in ['acme', 'acme_uri', 'domains_authenticators', 'renew_days']:
            cert.pop(key, None)

    if cert['type'] in (CA_TYPE_EXISTING, CA_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE):
        root_path = CERT_CA_ROOT_PATH
        is_ca = True
    else:
        root_path = CERT_ROOT_PATH
        is_ca = False

    cert.update({
        'root_path': root_path,
        'certificate_path': os.path.join(root_path, f'{cert["name"]}.crt'),
        'privatekey_path': os.path.join(root_path, f'{cert["name"]}.key'),
        'csr_path': os.path.join(root_path, f'{cert["name"]}.csr'),
        'cert_type': 'CA' if is_ca else 'CERTIFICATE',
        'revoked': bool(cert['revoked_date']),
        'internal': 'NO' if cert['type'] in (CA_TYPE_EXISTING, CERT_TYPE_EXISTING) else 'YES',
        'CA_type_existing': bool(cert['type'] & CA_TYPE_EXISTING),
        'CA_type_internal': bool(cert['type'] & CA_TYPE_INTERNAL),
        'CA_type_intermediate': bool(cert['type'] & CA_TYPE_INTERMEDIATE),
        'cert_type_existing': bool(cert['type'] & CERT_TYPE_EXISTING),
        'cert_type_internal': bool(cert['type'] & CERT_TYPE_INTERNAL),
        'cert_type_CSR': bool(cert['type'] & CERT_TYPE_CSR),

    })
    if is_ca:
        cert['crl_path'] = os.path.join(root_path, f'{cert["name"]}.crl')
