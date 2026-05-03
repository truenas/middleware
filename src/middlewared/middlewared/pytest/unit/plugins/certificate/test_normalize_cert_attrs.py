import pytest
from truenas_crypto_utils.csr import generate_certificate_signing_request
from truenas_crypto_utils.generate_certs import generate_certificate
from truenas_crypto_utils.generate_self_signed import generate_self_signed_certificate

from middlewared.api.base import query_result_item
from middlewared.api.current import CertificateEntry
from middlewared.plugins.certificate.query_utils import normalize_cert_attrs
from middlewared.plugins.certificate.utils import CERT_TYPE_CSR, CERT_TYPE_EXISTING

SUBJECT_DEFAULTS = {
    "country": "US",
    "state": "TN",
    "city": "Knoxville",
    "organization": "iXsystems",
    "organizational_unit": "dev",
    "common": "test.example.com",
    "email": "test@example.com",
    "san": ["DNS:test.example.com"],
    "lifetime": 365,
    "serial": 1,
    "key_type": "RSA",
    "key_length": 2048,
    "digest_algorithm": "SHA256",
}


@pytest.fixture(scope="module")
def signed_cert_pair():
    return generate_certificate(SUBJECT_DEFAULTS)


@pytest.fixture(scope="module")
def csr_pair():
    return generate_certificate_signing_request(SUBJECT_DEFAULTS)


@pytest.fixture(scope="module")
def ca_cert_pair():
    return generate_certificate({
        **SUBJECT_DEFAULTS,
        "common": "Test CA",
        "san": ["DNS:ca.example.com"],
        "cert_extensions": {
            "BasicConstraints": {"enabled": True, "ca": True, "extension_critical": True},
            "KeyUsage": {"enabled": True, "key_cert_sign": True, "crl_sign": True},
        },
    })


@pytest.fixture(scope="module")
def self_signed_pair():
    return generate_self_signed_certificate()


CORRUPT_CERT = (
    "-----BEGIN CERTIFICATE-----\n"
    "this is not valid base64 cert data\n"
    "-----END CERTIFICATE-----\n"
)
CORRUPT_CSR = (
    "-----BEGIN CERTIFICATE REQUEST-----\n"
    "this is not valid base64 csr data\n"
    "-----END CERTIFICATE REQUEST-----\n"
)


def make_row(*, name, type_flag, certificate=None, privatekey=None, csr=None, **extra):
    row = {
        "id": 1,
        "type": type_flag,
        "name": name,
        "certificate": certificate,
        "privatekey": privatekey,
        "CSR": csr,
        "acme_uri": None,
        "domains_authenticators": None,
        "renew_days": None,
        "acme": None,
        "add_to_trusted_store": False,
    }
    row.update(extra)
    return row


def validate_through_query_result_item(row):
    """Mimic CRUDServicePart._to_entry — instantiate the query-result model that strict-validates types."""
    return query_result_item(CertificateEntry)(**row)


def test_imported_certificate_with_key(signed_cert_pair):
    cert_pem, key_pem = signed_cert_pair
    row = make_row(
        name="imported_cert",
        type_flag=CERT_TYPE_EXISTING,
        certificate=cert_pem,
        privatekey=key_pem,
    )

    normalize_cert_attrs(row)

    assert row["parsed"] is True
    assert row["cert_type"] == "CERTIFICATE"
    assert row["cert_type_existing"] is True
    assert row["cert_type_CSR"] is False
    assert row["cert_type_CA"] is False
    assert row["certificate_path"] == "/etc/certificates/imported_cert.crt"
    assert row["privatekey_path"] == "/etc/certificates/imported_cert.key"
    assert row["csr_path"] is None
    assert len(row["chain_list"]) == 1
    assert row["chain_list"][0] in cert_pem
    assert row["key_type"] == "RSA"
    assert row["key_length"] == 2048
    assert row["common"] == "test.example.com"
    assert row["san"] == ["DNS:test.example.com"]
    assert row["digest_algorithm"] == "SHA256"
    assert row["fingerprint"] is not None
    assert row["from"] is not None
    assert row["until"] is not None
    assert isinstance(row["extensions"], dict)
    assert isinstance(row["serial"], int)

    entry = validate_through_query_result_item(row)
    assert entry.parsed is True
    assert entry.cert_type_CA is False


def test_imported_certificate_without_key(signed_cert_pair):
    cert_pem, _ = signed_cert_pair
    row = make_row(
        name="imported_no_key",
        type_flag=CERT_TYPE_EXISTING,
        certificate=cert_pem,
    )

    normalize_cert_attrs(row)

    assert row["parsed"] is True
    assert row["privatekey_path"] is None
    assert row["key_type"] is None
    assert row["key_length"] is None

    validate_through_query_result_item(row)


def test_csr(csr_pair):
    csr_pem, key_pem = csr_pair
    row = make_row(
        name="my_csr",
        type_flag=CERT_TYPE_CSR,
        csr=csr_pem,
        privatekey=key_pem,
    )

    normalize_cert_attrs(row)

    assert row["parsed"] is True
    assert row["cert_type_CSR"] is True
    assert row["cert_type_existing"] is False
    assert row["cert_type_CA"] is False
    assert row["csr_path"] == "/etc/certificates/my_csr.csr"
    assert row["certificate_path"] is None
    assert row["chain_list"] == []
    assert row["common"] == "test.example.com"
    # CSR-specific resets — fields that only make sense on signed certs
    assert row["from"] is None
    assert row["until"] is None
    assert row["fingerprint"] is None
    assert row["serial"] is None
    assert row["expired"] is None

    validate_through_query_result_item(row)


def test_acme_certificate(signed_cert_pair):
    """ACME certs are imported X.509 certs with ACME bookkeeping fields populated."""
    cert_pem, key_pem = signed_cert_pair
    row = make_row(
        name="acme_cert",
        type_flag=CERT_TYPE_EXISTING,
        certificate=cert_pem,
        privatekey=key_pem,
        acme_uri="https://acme-v02.api.letsencrypt.org/directory",
        acme={"id": 1, "directory": "letsencrypt"},
        domains_authenticators={"test.example.com": 1},
        renew_days=10,
    )

    normalize_cert_attrs(row)

    assert row["parsed"] is True
    assert row["acme_uri"] == "https://acme-v02.api.letsencrypt.org/directory"
    assert row["acme"] == {"id": 1, "directory": "letsencrypt"}
    assert row["domains_authenticators"] == {"test.example.com": 1}
    assert row["renew_days"] == 10
    assert isinstance(row["extensions"], dict)

    entry = validate_through_query_result_item(row)
    assert entry.acme_uri == "https://acme-v02.api.letsencrypt.org/directory"
    assert entry.renew_days == 10


def test_ca_certificate(ca_cert_pair):
    cert_pem, key_pem = ca_cert_pair
    row = make_row(
        name="ca_cert",
        type_flag=CERT_TYPE_EXISTING,
        certificate=cert_pem,
        privatekey=key_pem,
    )

    normalize_cert_attrs(row)

    assert row["parsed"] is True
    assert row["cert_type_CA"] is True
    assert "BasicConstraints" in row["extensions"]
    assert "CA:TRUE" in row["extensions"]["BasicConstraints"]

    entry = validate_through_query_result_item(row)
    assert entry.cert_type_CA is True


def test_self_signed_default_certificate(self_signed_pair):
    """The default UI cert generated by setup_self_signed_cert_for_ui_impl."""
    cert_pem, key_pem = self_signed_pair
    row = make_row(
        name="truenas_default",
        type_flag=CERT_TYPE_EXISTING,
        certificate=cert_pem,
        privatekey=key_pem,
    )

    normalize_cert_attrs(row)

    assert row["parsed"] is True
    assert row["common"] == "localhost"
    assert row["san"] == ["DNS:localhost"]
    assert row["organization"] == "iXsystems Inc. dba TrueNAS"

    validate_through_query_result_item(row)


def test_corrupt_certificate_does_not_break_pydantic_validation():
    """Regression test: a row whose certificate fails to parse must still survive query validation.

    The previous behavior (extensions=None) caused a Pydantic ValidationError because
    CertificateEntry.extensions is typed as required dict. The fix makes the failed_parsing
    branch set extensions={} so existing strict typing keeps holding.
    """
    row = make_row(
        name="broken_cert",
        type_flag=CERT_TYPE_EXISTING,
        certificate=CORRUPT_CERT,
    )

    normalize_cert_attrs(row)

    assert row["parsed"] is False
    assert row["extensions"] == {}
    # Every other parse-derived field is None
    for key in (
        "digest_algorithm", "lifetime", "country", "state", "city",
        "from", "until", "organization", "organizational_unit", "email",
        "common", "san", "serial", "fingerprint", "expired", "DN",
        "subject_name_hash", "chain",
    ):
        assert row[key] is None, f"expected {key!r} to be None on failed parse, got {row[key]!r}"

    # The actual regression check: this used to raise pydantic.ValidationError.
    entry = validate_through_query_result_item(row)
    assert entry.parsed is False
    assert entry.extensions == {}


def test_corrupt_csr_does_not_break_pydantic_validation():
    row = make_row(
        name="broken_csr",
        type_flag=CERT_TYPE_CSR,
        csr=CORRUPT_CSR,
    )

    normalize_cert_attrs(row)

    assert row["parsed"] is False
    assert row["cert_type_CSR"] is True
    assert row["extensions"] == {}

    entry = validate_through_query_result_item(row)
    assert entry.parsed is False
    assert entry.extensions == {}
