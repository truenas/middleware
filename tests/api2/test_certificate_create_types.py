import os

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.crypto import (
    generate_csr_pem,
    generate_self_signed_pem,
    get_cert_params,
    imported_certificate,
    imported_csr,
)
from middlewared.test.integration.utils import call
from truenas_api_client import ValidationErrors


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
