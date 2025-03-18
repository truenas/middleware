import datetime
import ipaddress
import random
import typing

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID

from middlewared.utils.time_utils import utc_now
from middlewared.validators import IpAddress

from .extensions_utils import add_extensions
from .key_utils import retrieve_signing_algorithm
from .load_utils import load_certificate, load_certificate_request, load_private_key
from .utils import DEFAULT_LIFETIME_DAYS, RDN_MAPPINGS


def generate_builder(options: dict) -> typing.Union[x509.CertificateBuilder, x509.CertificateSigningRequestBuilder]:
    # We expect backend_mapping keys for crypto_subject_name attr in options and for crypto_issuer_name as well
    data = {}
    for key in ('crypto_subject_name', 'crypto_issuer_name'):
        data[key] = x509.Name([
            x509.NameAttribute(getattr(NameOID, k.upper()), v)
            for k, v in (options.get(key) or {}).items() if v
        ])
    if not data['crypto_issuer_name']:
        data['crypto_issuer_name'] = data['crypto_subject_name']

    # Lifetime represents no of days
    # Let's normalize lifetime value
    not_valid_before = utc_now()
    not_valid_after = utc_now() + datetime.timedelta(
        days=options.get('lifetime') or DEFAULT_LIFETIME_DAYS
    )

    # Let's normalize `san`
    san = x509.SubjectAlternativeName([
        x509.IPAddress(ipaddress.ip_address(v)) if t == 'IP' else x509.DNSName(v)
        for t, v in options.get('san') or []
    ])

    builder = x509.CertificateSigningRequestBuilder if options.get('csr') else x509.CertificateBuilder

    cert = builder(
        subject_name=data['crypto_subject_name']
    )

    if not options.get('csr'):
        cert = cert.issuer_name(
            data['crypto_issuer_name']
        ).not_valid_before(
            not_valid_before
        ).not_valid_after(
            not_valid_after
        ).serial_number(options.get('serial') or random.randint(1000, pow(2, 30)))

    if san:
        cert = cert.add_extension(san, False)

    return cert


def normalize_san(san_list: list) -> list:
    # TODO: ADD MORE TYPES WRT RFC'S
    normalized = []
    ip_validator = IpAddress()
    for count, san in enumerate(san_list or []):
        # If we already have SAN normalized, let's use the normalized version and don't
        # try to add a type ourselves
        if ':' in san:
            san_type, san = san.split(':', 1)
        else:
            try:
                ip_validator(san)
            except ValueError:
                san_type = 'DNS'
            else:
                san_type = 'IP'
        normalized.append([san_type, san])

    return normalized
