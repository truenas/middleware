import contextlib
import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from middlewared.test.integration.utils import call


def get_cert_params():
    return {
        'key_type': 'RSA',
        'key_length': 4096,
        'san': ['domain1', '8.8.8.8'],
        'common': 'dev',
        'country': 'US',
        'state': 'TN',
        'city': 'Knoxville',
        'organization': 'iX',
        'organizational_unit': 'dev',
        'email': 'dev@ix.com',
        'digest_algorithm': 'SHA256',
        'cert_extensions': {},
    }


@contextlib.contextmanager
def certificate_signing_request(csr_name):
    cert_params = get_cert_params()
    csr = call('certificate.create', {
        'name': csr_name,
        'create_type': 'CERTIFICATE_CREATE_CSR',
        **cert_params,
    }, job=True)

    try:
        yield csr
    finally:
        call('certificate.delete', csr['id'], job=True)


def generate_csr_pem(common_name='test.local'):
    """Generate a fresh CSR + RSA private key as PEM strings for tests that
    need to import a CSR + key pair via CERTIFICATE_CREATE_IMPORTED_CSR."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'iX'),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(subject)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return csr_pem, key_pem


def generate_self_signed_pem(common_name='test.local'):
    """Generate a fresh self-signed certificate + key pair as PEM strings.

    Useful for CERTIFICATE_CREATE_IMPORTED tests so we don't ship hard-coded
    PEMs that eventually expire.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'iX'),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return cert_pem, key_pem


@contextlib.contextmanager
def imported_certificate(name, cert_pem=None, key_pem=None):
    """Context manager that creates an imported certificate via the API and
    cleans it up. If `cert_pem`/`key_pem` aren't provided, fresh material is
    generated."""
    if cert_pem is None or key_pem is None:
        cert_pem, key_pem = generate_self_signed_pem(common_name=name)
    cert = call('certificate.create', {
        'name': name,
        'create_type': 'CERTIFICATE_CREATE_IMPORTED',
        'certificate': cert_pem,
        'privatekey': key_pem,
    }, job=True)
    try:
        yield cert
    finally:
        call('certificate.delete', cert['id'], job=True)


@contextlib.contextmanager
def imported_csr(name, csr_pem, key_pem):
    """Context manager that imports an existing CSR + key pair via the API."""
    cert = call('certificate.create', {
        'name': name,
        'create_type': 'CERTIFICATE_CREATE_IMPORTED_CSR',
        'CSR': csr_pem,
        'privatekey': key_pem,
    }, job=True)
    try:
        yield cert
    finally:
        call('certificate.delete', cert['id'], job=True)
