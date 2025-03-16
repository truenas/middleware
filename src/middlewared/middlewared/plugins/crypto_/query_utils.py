import logging
import os

from cryptography.hazmat.primitives.asymmetric import dsa, ec, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .load_utils import load_certificate, load_certificate_request, load_private_key
from .utils import CERT_TYPE_EXISTING, CERT_TYPE_CSR, CERT_ROOT_PATH, RE_CERTIFICATE


logger = logging.getLogger(__name__)
CERT_REPORT_ERRORS = set()


def cert_extend_report_error(title: str, cert: dict) -> None:
    item = (title, cert['name'])
    if item not in CERT_REPORT_ERRORS:
        logger.debug('Failed to load %s of %s', title, cert['name'])


def normalize_cert_attrs(cert: dict) -> None:
    # Remove ACME related keys if cert is not an ACME based cert
    if not cert.get('acme'):
        for key in ['acme', 'acme_uri', 'domains_authenticators', 'renew_days']:
            cert.pop(key, None)

    root_path = CERT_ROOT_PATH
    cert.update({
        'root_path': root_path,
        'certificate_path': os.path.join(root_path, f'{cert["name"]}.crt'),
        'privatekey_path': os.path.join(root_path, f'{cert["name"]}.key'),
        'csr_path': os.path.join(root_path, f'{cert["name"]}.csr'),
        'cert_type': 'CERTIFICATE',
        'cert_type_existing': bool(cert['type'] & CERT_TYPE_EXISTING),
        'cert_type_CSR': bool(cert['type'] & CERT_TYPE_CSR),
        'chain_list': [],
        'key_length': None,
        'key_type': None,
    })

    certs = []
    if len(RE_CERTIFICATE.findall(cert['certificate'] or '')) >= 1:
        certs = RE_CERTIFICATE.findall(cert['certificate'])

    failed_parsing = False
    for c in certs:
        if c and load_certificate(c):
            cert['chain_list'].append(c)
        else:
            cert_extend_report_error('certificate chain', cert)
            break

    if certs:
        # This indicates cert is not CSR and a cert
        cert_data = load_certificate(cert['certificate'])
        cert.update(cert_data)
        if not cert_data:
            failed_parsing = True
            cert_extend_report_error('certificate', cert)

    if cert['privatekey']:
        key_obj = load_private_key(cert['privatekey'])
        if key_obj:
            if isinstance(key_obj, Ed25519PrivateKey):
                cert['key_length'] = 32
            else:
                cert['key_length'] = key_obj.key_size
            if isinstance(key_obj, (ec.EllipticCurvePrivateKey, Ed25519PrivateKey)):
                cert['key_type'] = 'EC'
            elif isinstance(key_obj, rsa.RSAPrivateKey):
                cert['key_type'] = 'RSA'
            elif isinstance(key_obj, dsa.DSAPrivateKey):
                cert['key_type'] = 'DSA'
            else:
                cert['key_type'] = 'OTHER'
        else:
            cert_extend_report_error('private key', cert)

    if cert['cert_type_CSR']:
        csr_data = load_certificate_request(cert['CSR'])
        if csr_data:
            cert.update({
                **csr_data,
                'from': None,
                'until': None,  # CSR's don't have from, until - normalizing keys
            })
        else:
            cert_extend_report_error('csr', cert)
            failed_parsing = True

    if failed_parsing:
        # Normalizing cert/csr
        # Should we perhaps set the value to something like "MALFORMED_CERTIFICATE" for this list off attrs ?
        cert.update({
            key: None for key in [
                'digest_algorithm', 'lifetime', 'country', 'state', 'city', 'from', 'until',
                'organization', 'organizational_unit', 'email', 'common', 'san', 'serial',
                'fingerprint', 'extensions', 'expired',
            ]
        })

    cert['parsed'] = not failed_parsing
