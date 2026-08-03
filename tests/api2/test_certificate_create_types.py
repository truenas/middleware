import os

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.crypto import (
    certificate_signing_request,
    generate_csr_pem,
    generate_self_signed_pem,
    get_cert_params,
    imported_certificate,
    imported_csr,
)
from middlewared.test.integration.utils import call
from truenas_api_client import ValidationErrors

# PEM blocks that pass the API's regex sniffing but fail to actually parse.
MALFORMED_CERT = "-----BEGIN CERTIFICATE-----\nZ2FyYmFnZQ==\n-----END CERTIFICATE-----\n"
MALFORMED_KEY = "-----BEGIN PRIVATE KEY-----\nZ2FyYmFnZQ==\n-----END PRIVATE KEY-----\n"
MALFORMED_CSR = "-----BEGIN CERTIFICATE REQUEST-----\nZ2FyYmFnZQ==\n-----END CERTIFICATE REQUEST-----\n"


@pytest.mark.parametrize("key_length", [2048, 4096])
def test_create_csr_rsa(key_length):
    params = {**get_cert_params(), "key_type": "RSA", "key_length": key_length}
    csr = call(
        "certificate.create",
        {
            "name": f"csr_rsa_{key_length}",
            "create_type": "CERTIFICATE_CREATE_CSR",
            **params,
        },
        job=True,
    )
    try:
        assert csr["cert_type_CSR"] is True, csr
        assert csr["parsed"] is True, csr
        assert csr["key_type"] == "RSA", csr
        assert csr["key_length"] == key_length, csr
    finally:
        call("certificate.delete", csr["id"], job=True)


@pytest.mark.parametrize("ec_curve", ["SECP256R1", "SECP384R1", "SECP521R1", "ed25519"])
def test_create_csr_ec(ec_curve):
    params = {**get_cert_params(), "key_type": "EC", "ec_curve": ec_curve}
    # key_length is irrelevant for EC; drop it
    params.pop("key_length", None)
    csr = call(
        "certificate.create",
        {
            "name": f"csr_ec_{ec_curve.lower()}",
            "create_type": "CERTIFICATE_CREATE_CSR",
            **params,
        },
        job=True,
    )
    try:
        assert csr["cert_type_CSR"] is True, csr
        assert csr["parsed"] is True, csr
        assert csr["key_type"] == "EC", csr
    finally:
        call("certificate.delete", csr["id"], job=True)


def test_create_csr_validation_empty_san():
    params = {**get_cert_params(), "san": []}
    with pytest.raises(ValidationErrors):
        call(
            "certificate.create",
            {
                "name": "csr_empty_san",
                "create_type": "CERTIFICATE_CREATE_CSR",
                **params,
            },
            job=True,
        )


def test_create_csr_validation_rsa_requires_key_length():
    params = {**get_cert_params(), "key_type": "RSA"}
    params.pop("key_length", None)
    with pytest.raises(ValidationErrors):
        call(
            "certificate.create",
            {
                "name": "csr_rsa_no_keylen",
                "create_type": "CERTIFICATE_CREATE_CSR",
                **params,
            },
            job=True,
        )


def test_create_csr_add_to_trusted_store_rejected():
    params = get_cert_params()
    with pytest.raises(ValidationErrors):
        call(
            "certificate.create",
            {
                "name": "csr_trusted_store",
                "create_type": "CERTIFICATE_CREATE_CSR",
                "add_to_trusted_store": True,
                **params,
            },
            job=True,
        )


def test_import_certificate_with_csr_pair():
    # Generate a CSR + key locally and import them via CERTIFICATE_CREATE_IMPORTED_CSR.
    # We can't round-trip a CSR's privatekey through certificate.query because
    # Secret-typed fields are redacted on the wire.
    csr_pem, key_pem = generate_csr_pem("imported.csr.local")
    with imported_csr("imported_csr_pair", csr_pem, key_pem) as imported:
        assert imported["cert_type_CSR"] is True, imported
        assert imported["name"] == "imported_csr_pair"


def test_import_certificate_duplicate_name():
    with imported_certificate("dup_name"):
        with pytest.raises(ValidationErrors):
            with imported_certificate("dup_name"):
                pass


@pytest.mark.parametrize("add_to_trusted_store_enabled", [True, False])
def test_import_certificate_add_to_trusted_store(add_to_trusted_store_enabled):
    # Replaces the legacy test that used CERTIFICATE_CREATE_INTERNAL + intermediate
    # CA helpers (both removed from the typesafe plugin). The behaviour under
    # test is the same: when add_to_trusted_store is True, the cert ends up at
    # /var/local/ca-certificates/cert_<name>.crt; when False, it does not.
    name = f"trusted_store_{add_to_trusted_store_enabled}"
    cert_pem, key_pem = generate_self_signed_pem(common_name=name)
    cert = call(
        "certificate.create",
        {
            "name": name,
            "create_type": "CERTIFICATE_CREATE_IMPORTED",
            "certificate": cert_pem,
            "privatekey": key_pem,
            "add_to_trusted_store": add_to_trusted_store_enabled,
        },
        job=True,
    )
    try:
        assert cert["add_to_trusted_store"] is add_to_trusted_store_enabled
        path = os.path.join("/var/local/ca-certificates", f"cert_{name}.crt")
        if add_to_trusted_store_enabled:
            assert call("filesystem.stat", path)
        else:
            with pytest.raises(CallError):
                call("filesystem.stat", path)
    finally:
        call("certificate.delete", cert["id"], job=True)


def test_create_csr_with_extensions():
    # Every enabled extension is instantiated with x509.extensions.<name>(...)
    # before the CSR is generated; make sure a fully populated set survives that.
    params = {
        **get_cert_params(),
        "cert_extensions": {
            "BasicConstraints": {"enabled": True, "ca": True, "extension_critical": True},
            "KeyUsage": {"enabled": True, "key_cert_sign": True, "digital_signature": True},
            "ExtendedKeyUsage": {"enabled": True, "usages": ["SERVER_AUTH"]},
        },
    }
    csr = call(
        "certificate.create",
        {"name": "csr_extensions", "create_type": "CERTIFICATE_CREATE_CSR", **params},
        job=True,
    )
    try:
        assert csr["cert_type_CSR"] is True, csr
        assert csr["parsed"] is True, csr
        assert "CA:TRUE" in csr["extensions"]["BasicConstraints"], csr
        assert "TLS Web Server Authentication" in csr["extensions"]["ExtendedKeyUsage"], csr
        assert "Certificate Sign" in csr["extensions"]["KeyUsage"], csr
    finally:
        call("certificate.delete", csr["id"], job=True)


@pytest.mark.parametrize(
    "cert_extensions,error_attribute",
    [
        (
            # RFC 5280 requires ca to be set whenever key_cert_sign is.
            {"KeyUsage": {"enabled": True, "key_cert_sign": True}},
            "certificate_create.BasicConstraints",
        ),
        (
            {"ExtendedKeyUsage": {"enabled": True, "usages": []}},
            "certificate_create.ExtendedKeyUsage.usages",
        ),
        (
            # path_length is only meaningful for a CA certificate, so x509
            # refuses to build the extension.
            {"BasicConstraints": {"enabled": True, "ca": False, "path_length": 2}},
            "certificate_create.BasicConstraints",
        ),
    ],
    ids=["key_cert_sign_without_ca", "extended_key_usage_without_usages", "path_length_without_ca"],
)
def test_create_csr_invalid_extensions(cert_extensions, error_attribute):
    params = {**get_cert_params(), "cert_extensions": cert_extensions}
    with pytest.raises(ValidationErrors) as ve:
        call(
            "certificate.create",
            {"name": "csr_bad_extensions", "create_type": "CERTIFICATE_CREATE_CSR", **params},
            job=True,
        )
    assert any(e.attribute == error_attribute for e in ve.value.errors), ve.value.errors


def test_import_certificate_without_certificate():
    with pytest.raises(ValidationErrors) as ve:
        call(
            "certificate.create",
            {"name": "import_no_cert", "create_type": "CERTIFICATE_CREATE_IMPORTED"},
            job=True,
        )
    assert any(e.attribute == "certificate_create.certificate" for e in ve.value.errors), ve.value.errors


def test_import_certificate_with_malformed_certificate():
    with pytest.raises(ValidationErrors) as ve:
        call(
            "certificate.create",
            {
                "name": "import_bad_cert",
                "create_type": "CERTIFICATE_CREATE_IMPORTED",
                "certificate": MALFORMED_CERT,
                "privatekey": generate_self_signed_pem()[1],
            },
            job=True,
        )
    assert any(e.attribute == "certificate_create.certificate" for e in ve.value.errors), ve.value.errors


def test_import_certificate_with_malformed_private_key():
    cert_pem, _ = generate_self_signed_pem(common_name="import.bad.key")
    with pytest.raises(ValidationErrors) as ve:
        call(
            "certificate.create",
            {
                "name": "import_bad_key",
                "create_type": "CERTIFICATE_CREATE_IMPORTED",
                "certificate": cert_pem,
                "privatekey": MALFORMED_KEY,
            },
            job=True,
        )
    assert any(e.attribute == "certificate_create.privatekey" for e in ve.value.errors), ve.value.errors


def test_import_certificate_without_private_key():
    # The private key is optional for an imported certificate; the entry is
    # then reported without a private key path or key details.
    cert_pem, _ = generate_self_signed_pem(common_name="import.no.key")
    cert = call(
        "certificate.create",
        {
            "name": "import_no_key",
            "create_type": "CERTIFICATE_CREATE_IMPORTED",
            "certificate": cert_pem,
        },
        job=True,
    )
    try:
        assert cert["parsed"] is True, cert
        assert cert["privatekey_path"] is None, cert
        assert cert["key_length"] is None, cert
        assert cert["key_type"] is None, cert
    finally:
        call("certificate.delete", cert["id"], job=True)


def test_import_ca_certificate():
    cert_pem, key_pem = generate_self_signed_pem(common_name="import.ca", ca=True)
    with imported_certificate("import_ca", cert_pem, key_pem) as cert:
        assert cert["cert_type_CA"] is True, cert
        assert cert["parsed"] is True, cert


def test_import_csr_with_malformed_csr():
    with pytest.raises(ValidationErrors) as ve:
        call(
            "certificate.create",
            {
                "name": "import_bad_csr",
                "create_type": "CERTIFICATE_CREATE_IMPORTED_CSR",
                "CSR": MALFORMED_CSR,
                "privatekey": generate_self_signed_pem()[1],
            },
            job=True,
        )
    assert any(e.attribute == "certificate_create.CSR" for e in ve.value.errors), ve.value.errors


def test_import_csr_without_private_key():
    # Unlike an imported certificate, an imported CSR must come with its key.
    csr_pem, _ = generate_csr_pem("import.csr.nokey")
    with pytest.raises(ValidationErrors) as ve:
        call(
            "certificate.create",
            {
                "name": "import_csr_no_key",
                "create_type": "CERTIFICATE_CREATE_IMPORTED_CSR",
                "CSR": csr_pem,
            },
            job=True,
        )
    assert any(e.attribute == "certificate_create.privatekey" for e in ve.value.errors), ve.value.errors


def test_create_csr_invalid_country():
    params = {**get_cert_params(), "country": "ZZZZ"}
    with pytest.raises(ValidationErrors) as ve:
        call(
            "certificate.create",
            {"name": "csr_bad_country", "create_type": "CERTIFICATE_CREATE_CSR", **params},
            job=True,
        )
    assert any(e.attribute == "certificate_create.country" for e in ve.value.errors), ve.value.errors


def test_create_acme_certificate_with_unknown_csr_id():
    with pytest.raises(ValidationErrors) as ve:
        call(
            "certificate.create",
            {
                "name": "acme_bad_csr_id",
                "create_type": "CERTIFICATE_CREATE_ACME",
                "csr_id": 999999,
                "tos": True,
                "acme_directory_uri": "https://acme.test.invalid/directory",
            },
            job=True,
        )
    assert any(e.attribute == "certificate_create.csr_id" for e in ve.value.errors), ve.value.errors


def test_create_acme_certificate_without_csr_id():
    # csr_id is optional in the create model but mandatory for the ACME handler.
    with pytest.raises(ValidationErrors) as ve:
        call(
            "certificate.create",
            {
                "name": "acme_no_csr_id",
                "create_type": "CERTIFICATE_CREATE_ACME",
                "tos": True,
                "acme_directory_uri": "https://acme.test.invalid/directory",
            },
            job=True,
        )
    assert any(e.attribute == "certificate_create.csr_id" for e in ve.value.errors), ve.value.errors


@pytest.mark.parametrize(
    "acme_directory_uri",
    ["https://acme.test.invalid/directory", "https://acme.test.invalid/directory/"],
    ids=["without_trailing_slash", "with_trailing_slash"],
)
def test_create_acme_certificate_requires_dns_mapping(acme_directory_uri):
    # With a usable csr_id the request reaches the ACME handler, which refuses
    # to talk to the ACME server until every domain in the CSR has a DNS
    # authenticator assigned to it.
    with certificate_signing_request("acme_csr_source") as csr:
        with pytest.raises(ValidationErrors) as ve:
            call(
                "certificate.create",
                {
                    "name": "acme_no_dns_mapping",
                    "create_type": "CERTIFICATE_CREATE_ACME",
                    "csr_id": csr["id"],
                    "tos": True,
                    "acme_directory_uri": acme_directory_uri,
                },
                job=True,
            )
        assert any(e.attribute == "acme_create.dns_mapping" for e in ve.value.errors), ve.value.errors
