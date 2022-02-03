import copy
import logging
import os

from collections import defaultdict
from cryptography.hazmat.primitives.asymmetric import dsa, ec, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from typing import Union

from .load_utils import load_certificate, load_certificate_request, load_private_key
from .utils import (
    CA_TYPE_EXISTING, CA_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE, CERT_TYPE_EXISTING, CERT_TYPE_INTERNAL,
    CERT_TYPE_CSR, CERT_ROOT_PATH, CERT_CA_ROOT_PATH, RE_CERTIFICATE
)


logger = logging.getLogger(__name__)
CERT_REPORT_ERRORS = set()


def cert_extend_report_error(title: str, cert: dict) -> None:
    item = (title, cert['name'])
    if item not in CERT_REPORT_ERRORS:
        logger.debug('Failed to load %s of %s', title, cert['name'])


def cert_issuer(cert: dict) -> Union[str, dict]:
    issuer = None
    if cert['type'] in (CA_TYPE_EXISTING, CERT_TYPE_EXISTING):
        issuer = 'external'
    elif cert['type'] == CA_TYPE_INTERNAL:
        issuer = 'self-signed'
    elif cert['type'] in (CERT_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE):
        issuer = cert['signedby']
    elif cert['type'] == CERT_TYPE_CSR:
        issuer = 'external - signature pending'
    return issuer


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
        'can_be_revoked': bool(cert['privatekey']) and not bool(cert['revoked_date']) if is_ca else (
            bool(cert['signedby']) and not bool(cert['revoked_date'])
        ),
        'internal': 'NO' if cert['type'] in (CA_TYPE_EXISTING, CERT_TYPE_EXISTING) else 'YES',
        'CA_type_existing': bool(cert['type'] & CA_TYPE_EXISTING),
        'CA_type_internal': bool(cert['type'] & CA_TYPE_INTERNAL),
        'CA_type_intermediate': bool(cert['type'] & CA_TYPE_INTERMEDIATE),
        'cert_type_existing': bool(cert['type'] & CERT_TYPE_EXISTING),
        'cert_type_internal': bool(cert['type'] & CERT_TYPE_INTERNAL),
        'cert_type_CSR': bool(cert['type'] & CERT_TYPE_CSR),
        'issuer': cert_issuer(cert),
        'chain_list': [],
        'key_length': None,
        'key_type': None,
    })
    if is_ca:
        cert['crl_path'] = os.path.join(root_path, f'{cert["name"]}.crl')

    certs = []
    if len(RE_CERTIFICATE.findall(cert['certificate'] or '')) > 1:
        certs = RE_CERTIFICATE.findall(cert['certificate'])
    elif cert['type'] != CERT_TYPE_CSR:
        certs = [cert['certificate']]
        signing_CA = cert['issuer']
        # Recursively get all internal/intermediate certificates
        # FIXME: NONE HAS BEEN ADDED IN THE FOLLOWING CHECK FOR CSR'S WHICH HAVE BEEN SIGNED BY A CA
        while signing_CA not in ['external', 'self-signed', 'external - signature pending', None]:
            certs.append(signing_CA['certificate'])
            signing_CA['issuer'] = cert_issuer(signing_CA)
            signing_CA = signing_CA['issuer']

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
                'fingerprint', 'extensions'
            ]
        })

    cert['parsed'] = not failed_parsing


def get_ca_chain(ca_id: int, certs: list, cas: list) -> list:
    cert_mapping = defaultdict(list)
    cas_mapping = defaultdict(list)
    cas_id_mapping = {}
    for cert in filter(lambda c: c['signedby'], certs):
        cert_mapping[cert['signedby']['id']].append({**cert, 'cert_type': 'CERTIFICATE'})

    for ca in cas:
        cas_id_mapping[ca['id']] = ca
        if ca['signedby']:
            cas_mapping[ca['signedby']['id']].append(ca)

    return get_ca_chain_impl(ca_id, cas_id_mapping, cert_mapping, cas_mapping)


def get_ca_chain_impl(ca_id: int, cas: dict, certs_mapping: dict, cas_mapping: dict) -> list:
    certs = copy.deepcopy(certs_mapping[ca_id])
    for ca in cas_mapping[ca_id]:
        certs.extend(get_ca_chain_impl(ca['id'], cas, certs_mapping, cas_mapping))

    certs.append({**cas[ca_id], 'cert_type': 'CA'})
    return certs
