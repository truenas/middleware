import pytest

from middlewared.test.integration.assets.crypto import (
    acme_registration,
    certificate_signing_request,
    datastore_certificate,
    generate_self_signed_pem,
    imported_certificate,
)
from middlewared.test.integration.utils import call
from truenas_api_client import ClientException, ValidationErrors


@pytest.fixture(scope="function")
def acme_certificate():
    """An ACME certificate backed by a fake ACME registration."""
    with acme_registration() as registration_id:
        cert_pem, key_pem = generate_self_signed_pem(common_name="acme.test.local")
        with datastore_certificate(
            "acme_cert",
            certificate=cert_pem,
            privatekey=key_pem,
            acme=registration_id,
            acme_uri="http://127.0.0.1/cert/1",
            domains_authenticators={"acme.test.local": 42},
            renew_days=10,
        ) as cert:
            yield cert


def test_update_certificate_rename():
    with certificate_signing_request("rename_src") as csr:
        updated = call(
            "certificate.update", csr["id"], {"name": "rename_dst"}, job=True
        )
        assert updated["name"] == "rename_dst", updated
        # The fixture's finally calls certificate.delete on csr['id'] which is fine
        # — id stays the same after rename.


def test_update_certificate_rename_collision():
    with imported_certificate("rename_target"):
        with certificate_signing_request("rename_other") as csr:
            with pytest.raises(ValidationErrors):
                call(
                    "certificate.update", csr["id"], {"name": "rename_target"}, job=True
                )


def test_update_renew_days_rejected_for_non_acme():
    with certificate_signing_request("renew_days_target") as csr:
        with pytest.raises(ValidationErrors):
            call("certificate.update", csr["id"], {"renew_days": 5}, job=True)


def test_update_certificate_no_changes():
    # None of the updatable fields change, so validation and the datastore
    # write are both skipped and the entry comes back untouched.
    with certificate_signing_request("update_noop") as csr:
        updated = call("certificate.update", csr["id"], {}, job=True)
        assert updated["name"] == csr["name"], updated
        assert updated["add_to_trusted_store"] == csr["add_to_trusted_store"], updated


def test_update_csr_add_to_trusted_store_rejected():
    with certificate_signing_request("update_trusted_store") as csr:
        with pytest.raises(ValidationErrors) as ve:
            call("certificate.update", csr["id"], {"add_to_trusted_store": True}, job=True)
        assert any(
            e.attribute == "certificate_update.add_to_trusted_store" for e in ve.value.errors
        ), ve.value.errors


def test_update_certificate_used_by_truenas_connect():
    with imported_certificate("tnc_owned") as cert:
        call("datastore.update", "truenas_connect", 1, {"certificate": cert["id"]})
        try:
            with pytest.raises(ValidationErrors) as ve:
                call("certificate.update", cert["id"], {"name": "tnc_owned_renamed"}, job=True)
            assert any(
                e.attribute == "certificate_update.name" for e in ve.value.errors
            ), ve.value.errors
        finally:
            call("datastore.update", "truenas_connect", 1, {"certificate": None})


def test_update_acme_certificate_renew_days(acme_certificate):
    # renew_days is only writable on ACME certificates.
    updated = call("certificate.update", acme_certificate["id"], {"renew_days": 15}, job=True)
    assert updated["renew_days"] == 15, updated


def test_delete_certificate_in_use():
    # The web UI always holds a reference to the configured UI certificate, so
    # deleting it must be refused.
    ui_cert_id = call("system.general.config")["ui_certificate"]
    with pytest.raises(ClientException, match="being used by following service"):
        call("certificate.delete", ui_cert_id, job=True)


def test_delete_acme_certificate_revocation_failure(acme_certificate):
    # Revocation is attempted against the (fake) ACME server and fails; without
    # `force` that aborts the delete, with `force` the entry goes away anyway.
    with pytest.raises(ClientException, match="Failed to revoke certificate"):
        call("certificate.delete", acme_certificate["id"], job=True)
    assert call("certificate.query", [["id", "=", acme_certificate["id"]]]), "certificate was deleted anyway"

    assert call("certificate.delete", acme_certificate["id"], True, job=True) is True
    assert not call("certificate.query", [["id", "=", acme_certificate["id"]]])


def test_delete_domains_authenticator(acme_certificate):
    assert acme_certificate["domains_authenticators"] == {"acme.test.local": 42}
    other_pem, other_key_pem = generate_self_signed_pem(common_name="other.acme.test.local")
    with datastore_certificate(
        "acme_cert_other",
        certificate=other_pem,
        privatekey=other_key_pem,
        acme=acme_certificate["acme"]["id"],
        domains_authenticators={"other.acme.test.local": 7},
    ) as other:
        call("certificate.delete_domains_authenticator", 42)

        updated = call("certificate.query", [["id", "=", acme_certificate["id"]]], {"get": True})
        assert updated["domains_authenticators"] == {}, updated
        # Certificates that do not reference the authenticator are untouched.
        untouched = call("certificate.query", [["id", "=", other["id"]]], {"get": True})
        assert untouched["domains_authenticators"] == {"other.acme.test.local": 7}, untouched
