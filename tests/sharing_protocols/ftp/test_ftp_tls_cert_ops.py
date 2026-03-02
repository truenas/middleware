"""FTP TLS certificate type detection – live FTPS operations tests.

Validates that a live FTPS session works end-to-end (login, directory
listing, file upload/download) for both RSA and EC certificates.

Two parametrized variants:

  rsa_cert  – RSA 2048-bit certificate
  ec_cert   – EC P-256 certificate

Before the tls.conf.mako fix:
  rsa_cert tests PASS  (RSA directives are always written)
  ec_cert  tests FAIL  (RSA directives are written instead of EC directives,
                        ProFTPD cannot use an EC key via TLSRSACertificate*)

After the fix both variants PASS.
"""
import contextlib
import io
from types import SimpleNamespace

import pytest

from middlewared.test.integration.assets.account import user as ftp_user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server

from protocols import ftps_connection


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FTP_USERNAME = "ftpstlstest"
_FTP_PASSWORD = "Ftps@TLStest1"   # meets any complexity requirements


# ---------------------------------------------------------------------------
# Certificate helpers
# ---------------------------------------------------------------------------

def _generate_self_signed_cert(key_type: str, cert_path: str, key_path: str) -> None:
    """Run openssl on the TrueNAS host to produce a self-signed certificate.

    basicConstraints=CA:FALSE is required because openssl sets CA:TRUE by
    default, which causes the middleware to classify the cert as a CA and
    reject it in cert_services_validation.
    """
    if key_type == "RSA":
        ssh(
            f"openssl req -x509 -newkey rsa:2048"
            f" -keyout {key_path} -out {cert_path}"
            f" -sha256 -days 365 -nodes"
            f' -subj "/CN=ftp-tls-test-rsa"'
            f' -addext "basicConstraints=CA:FALSE"'
            f" 2>/dev/null"
        )
    elif key_type == "EC":
        ssh(f"openssl ecparam -genkey -name prime256v1 -noout -out {key_path}")
        ssh(
            f"openssl req -x509 -new -key {key_path}"
            f" -out {cert_path}"
            f" -sha256 -days 365 -nodes"
            f' -subj "/CN=ftp-tls-test-ec"'
            f' -addext "basicConstraints=CA:FALSE"'
            f" 2>/dev/null"
        )
    else:
        raise ValueError(f"Unsupported key_type: {key_type!r}")


def _clear_ftp_cert_ref(cert_id: int) -> None:
    """Clear any FTP reference to *cert_id* so check_cert_deps will not block
    certificate deletion.  Setting ssltls_certificate=None (not just tls=False)
    is required because check_cert_deps inspects the stored ID regardless of
    the tls flag.
    """
    try:
        ftp_config = call("ftp.config")
        if ftp_config.get("ssltls_certificate") == cert_id:
            call("ftp.update", {"tls": False, "ssltls_certificate": None})
    except Exception:
        pass


def _delete_cert_by_name(name: str) -> None:
    """Delete any existing certificate with *name*, ignoring errors.

    Used to remove stale certificates from a previously failed test run.
    Any FTP reference is cleared first so check_cert_deps does not block.
    """
    for cert in call("certificate.query", [["name", "=", name]]):
        try:
            _clear_ftp_cert_ref(cert["id"])
            call("certificate.delete", cert["id"], True, job=True)
        except Exception:
            pass


@contextlib.contextmanager
def imported_certificate(name: str, key_type: str):
    """Generate, import, and (on exit) delete a self-signed certificate.

    Pre-cleans any stale certificate with the same name before creation.
    Yields the certificate dict returned by certificate.create.
    """
    cert_path = f"/tmp/ftp-tls-test-{key_type.lower()}-cert.pem"
    key_path = f"/tmp/ftp-tls-test-{key_type.lower()}-key.pem"

    _delete_cert_by_name(name)

    try:
        _generate_self_signed_cert(key_type, cert_path, key_path)
        certificate_pem = ssh(f"cat {cert_path}")
        privatekey_pem = ssh(f"cat {key_path}")

        cert = call(
            "certificate.create",
            {
                "name": name,
                "create_type": "CERTIFICATE_CREATE_IMPORTED",
                "certificate": certificate_pem,
                "privatekey": privatekey_pem,
            },
            job=True,
        )
        try:
            yield cert
        finally:
            try:
                call("certificate.delete", cert["id"], True, job=True)
            except Exception:
                pass
    finally:
        ssh(f"rm -f {cert_path} {key_path}", check=False)


# ---------------------------------------------------------------------------
# FTP service helpers
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def ftp_tls_enabled(cert_id: int, extra_config: dict | None = None):
    """Configure FTP TLS with *cert_id*, start the service, restore on exit.

    *extra_config* is merged into the ftp.update call so callers can add
    settings such as onlylocal=True without a separate update.

    Cleanup is structured in two layers:
      - inner  finally: service.control STOP  (only if START succeeded)
      - outer  finally: ftp.update restore    (always, including if START fails)
    """
    original = call("ftp.config")

    # Always restore ssltls_certificate including None; leaving it set to the
    # test cert ID (even with tls=False) blocks certificate.delete via
    # check_cert_deps.
    restore_keys = ["tls", "tls_policy", "tls_opt_no_session_reuse_required",
                    "ssltls_certificate", "onlylocal", "onlyanonymous"]
    restore = {k: original[k] for k in restore_keys}

    call(
        "ftp.update",
        {
            "tls": True,
            "tls_policy": "on",
            "tls_opt_no_session_reuse_required": True,
            "ssltls_certificate": cert_id,
            **(extra_config or {}),
        },
    )

    try:
        call("service.control", "START", "ftp", {"silent": False}, job=True)
        try:
            yield
        finally:
            call("service.control", "STOP", "ftp", {"silent": False}, job=True)
    finally:
        call("ftp.update", restore)


@contextlib.contextmanager
def ftps_test_environment(cert_id: int, key_type: str):
    """Full FTPS test environment: dataset + user + TLS service + connection.

    Layers (innermost cleaned up first):
      dataset  →  ftp_user  →  ftp service with TLS  →  FTPS connection

    Yields a SimpleNamespace with:
      .ftps          – authenticated FTP_TLS object ready for commands
      .username      – local username
      .password      – password
      .dataset_path  – path to the home/data directory on the server
    """
    ftp_group_id = call(
        "group.query",
        [["name", "=", "ftp"], ["local", "=", True]],
        {"get": True},
    )["id"]

    with dataset(f"ftpstls-{key_type.lower()}") as ds:
        ds_path = f"/mnt/{ds}"
        # World-writable so the test user can upload files.
        ssh(f"chmod 777 {ds_path}")

        with ftp_user({
            "username": _FTP_USERNAME,
            "group_create": True,
            "home": ds_path,
            "full_name": "FTPS TLS Test",
            "password": _FTP_PASSWORD,
            "home_create": False,
            "groups": [ftp_group_id],
        }):
            with ftp_tls_enabled(
                cert_id,
                extra_config={"onlylocal": True, "onlyanonymous": False},
            ):
                with ftps_connection(truenas_server.ip) as ftps:
                    ftps.login(_FTP_USERNAME, _FTP_PASSWORD)
                    yield SimpleNamespace(
                        ftps=ftps,
                        username=_FTP_USERNAME,
                        password=_FTP_PASSWORD,
                        dataset_path=ds_path,
                    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key_type", ["RSA", "EC"], ids=["rsa_cert", "ec_cert"])
def test_ftp_tls_ftps_operations(key_type):
    """A live FTPS session must work end-to-end with the configured certificate.

    Tests:
      - Authenticated login over TLS
      - Directory listing (MLSD)
      - File upload   (STOR via storbinary)
      - File presence verified in subsequent listing
      - File deletion (DELE)

    ec_cert is expected to FAIL on unpatched code because ProFTPD cannot load
    an EC key via TLSRSACertificate* directives, so the TLS handshake will
    fail before login is reached.
    """
    cert_name = f"ftp-tls-proto-{key_type.lower()}"

    with imported_certificate(cert_name, key_type) as cert:
        assert cert["key_type"] == key_type, (
            f"cert key_type={cert['key_type']!r}, expected {key_type!r}"
        )

        with ftps_test_environment(cert["id"], key_type) as env:
            ftps = env.ftps

            # ---- directory listing ----
            entries = dict(ftps.mlsd())
            # '.' and '..' are always present; no user files yet.
            assert "." in entries, "MLSD did not return current-directory entry"

            # ---- upload a small file ----
            test_filename = f"tls_test_{key_type.lower()}.txt"
            test_content = f"FTPS TLS test file – key type {key_type}\n".encode()
            ftps.storbinary(f"STOR {test_filename}", io.BytesIO(test_content))

            # ---- verify the upload appears in the listing ----
            entries = dict(ftps.mlsd())
            assert test_filename in entries, (
                f"Uploaded file {test_filename!r} not found in MLSD listing; "
                f"entries: {sorted(entries)}"
            )

            # ---- delete the test file ----
            ftps.delete(test_filename)

            entries = dict(ftps.mlsd())
            assert test_filename not in entries, (
                f"Deleted file {test_filename!r} still appears in MLSD listing"
            )
