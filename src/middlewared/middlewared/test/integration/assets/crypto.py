import contextlib
import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed448, ed25519, rsa
from cryptography.x509.oid import NameOID
import josepy as jose

from middlewared.test.integration.utils import call

# `cert_type` bit flags used by the `system.certificate` datastore table.
CERT_TYPE_EXISTING = 0x08
CERT_TYPE_CSR = 0x20


def get_cert_params():
    return {
        "key_type": "RSA",
        "key_length": 4096,
        "san": ["domain1", "8.8.8.8"],
        "common": "dev",
        "country": "US",
        "state": "TN",
        "city": "Knoxville",
        "organization": "iX",
        "organizational_unit": "dev",
        "email": "dev@ix.com",
        "digest_algorithm": "SHA256",
        "cert_extensions": {},
    }


@contextlib.contextmanager
def certificate_signing_request(csr_name):
    cert_params = get_cert_params()
    csr = call(
        "certificate.create",
        {
            "name": csr_name,
            "create_type": "CERTIFICATE_CREATE_CSR",
            **cert_params,
        },
        job=True,
    )

    try:
        yield csr
    finally:
        call("certificate.delete", csr["id"], job=True)


def generate_csr_pem(common_name="test.local"):
    """Generate a fresh CSR + RSA private key as PEM strings for tests that
    need to import a CSR + key pair via CERTIFICATE_CREATE_IMPORTED_CSR."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "iX"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
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


def private_key_pem(key):
    """PKCS#8 PEM serialization of any `cryptography` private key object."""
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def generate_self_signed_pem(
    common_name="test.local",
    *,
    key=None,
    organization="iX",
    san=None,
    ca=False,
    expired=False,
):
    """Generate a fresh self-signed certificate + key pair as PEM strings.

    Useful for CERTIFICATE_CREATE_IMPORTED tests so we don't ship hard-coded
    PEMs that eventually expire.

    `key` accepts any `cryptography` private key object so that callers can
    exercise the non-RSA key handling in the certificate query code; `ca`
    stamps a `CA:TRUE` BasicConstraints extension and `expired` back-dates the
    validity window so the certificate is already expired. Passing
    `common_name=None` and `san=[]` produces a certificate that carries no
    domain names at all.
    """
    if key is None:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    attributes = [
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
    ]
    if common_name is not None:
        attributes.append(x509.NameAttribute(NameOID.COMMON_NAME, common_name))
    subject = issuer = x509.Name(attributes)
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=400))
        .not_valid_after(now - datetime.timedelta(days=1) if expired else now + datetime.timedelta(days=365))
    )
    san_names = [common_name] if san is None else san
    if san_names:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(n) for n in san_names]),
            critical=False,
        )
    if ca:
        builder = builder.add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    # Ed25519/Ed448 carry their own hash and must be signed with `algorithm=None`.
    algorithm = None if isinstance(key, (ed25519.Ed25519PrivateKey, ed448.Ed448PrivateKey)) else hashes.SHA256()
    cert = builder.sign(key, algorithm)
    return cert.public_bytes(serialization.Encoding.PEM).decode(), private_key_pem(key)


@contextlib.contextmanager
def imported_certificate(name, cert_pem=None, key_pem=None):
    """Context manager that creates an imported certificate via the API and
    cleans it up. If `cert_pem`/`key_pem` aren't provided, fresh material is
    generated."""
    if cert_pem is None or key_pem is None:
        cert_pem, key_pem = generate_self_signed_pem(common_name=name)
    cert = call(
        "certificate.create",
        {
            "name": name,
            "create_type": "CERTIFICATE_CREATE_IMPORTED",
            "certificate": cert_pem,
            "privatekey": key_pem,
        },
        job=True,
    )
    try:
        yield cert
    finally:
        call("certificate.delete", cert["id"], job=True)


@contextlib.contextmanager
def imported_csr(name, csr_pem, key_pem):
    """Context manager that imports an existing CSR + key pair via the API."""
    cert = call(
        "certificate.create",
        {
            "name": name,
            "create_type": "CERTIFICATE_CREATE_IMPORTED_CSR",
            "CSR": csr_pem,
            "privatekey": key_pem,
        },
        job=True,
    )
    try:
        yield cert
    finally:
        call("certificate.delete", cert["id"], job=True)


@contextlib.contextmanager
def datastore_certificate(name, cert_type=CERT_TYPE_EXISTING, **columns):
    """Insert a certificate row straight into the datastore and yield the queried entry.

    `certificate.create` validates its input, so material it rejects (malformed
    PEMs, expired certificates, exotic key types, ACME certificates) can only be
    put in front of the query/normalization code this way.
    """
    id_ = call(
        "datastore.insert",
        "system.certificate",
        {"name": name, "type": cert_type, **columns},
        {"prefix": "cert_"},
    )
    try:
        yield call("certificate.query", [["id", "=", id_]], {"get": True})
    finally:
        # datastore.delete rather than certificate.delete: the entry may be
        # unparseable or in use, and neither should fail the cleanup.
        call("datastore.delete", "system.certificate", id_)


@contextlib.contextmanager
def acme_registration():
    """Register a fake ACME directory and yield its datastore ID.

    Certificates pointed at it look like ACME certificates to the middleware
    without any of them ever having been issued by a real ACME server. The URIs
    resolve to the local nginx, so an ACME client built from this registration
    fails with a regular `CallError` instead of a connection error.
    """
    key = jose.JWKRSA(key=jose.ComparableRSAKey(rsa.generate_private_key(public_exponent=65537, key_size=2048)))
    id_ = call(
        "datastore.insert",
        "system.acmeregistration",
        {
            "uri": "http://127.0.0.1/acme-acct",
            "directory": "https://acme.test.invalid/directory/",
            "tos": "http://127.0.0.1/tos",
            "new_account_uri": "http://127.0.0.1/new-acct",
            "new_nonce_uri": "http://127.0.0.1/new-nonce",
            "new_order_uri": "http://127.0.0.1/new-order",
            "revoke_cert_uri": "http://127.0.0.1/revoke-cert",
        },
    )
    body_id = call(
        "datastore.insert",
        "system.acmeregistrationbody",
        {"status": "valid", "key": key.json_dumps(), "acme": id_},
    )
    try:
        yield id_
    finally:
        call("datastore.delete", "system.acmeregistrationbody", body_id)
        call("datastore.delete", "system.acmeregistration", id_)


@contextlib.contextmanager
def ui_certificate(cert_id):
    """Point the web UI at `cert_id` for the duration of the block, then restore."""
    general_config = call("system.general.config")
    call("datastore.update", "system.settings", general_config["id"], {"stg_guicertificate": cert_id})
    try:
        yield cert_id
    finally:
        call(
            "datastore.update",
            "system.settings",
            general_config["id"],
            {"stg_guicertificate": general_config["ui_certificate"]},
        )
        call("service.control", "START", "ssl", job=True)
