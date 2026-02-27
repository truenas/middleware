"""Tests for FTP TLS certificate type detection (RSA vs EC).

The bug (NAS-XXXXX): When configuring FTP TLS, tls.conf.mako always emits
TLSRSACertificateFile / TLSRSACertificateKeyFile regardless of whether the
selected certificate is RSA or EC.  ProFTPD ignores those directives for EC
keys, so FTPS silently breaks when an EC certificate is chosen.

What should happen:
  - RSA certificate  → TLSRSACertificateFile / TLSRSACertificateKeyFile
  - EC  certificate  → TLSECCertificateFile  / TLSECCertificateKeyFile

These tests validate both cases.  Running them BEFORE the fix is applied is
intentional:

  RSA test  – expected to PASS  (current code always writes RSA directives)
  EC  test  – expected to FAIL  (current code still writes RSA directives)

After the fix both tests must PASS.
"""
import contextlib

import pytest

from middlewared.test.integration.utils import call, ssh


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_self_signed_cert(key_type: str, cert_path: str, key_path: str) -> None:
    """Run openssl on the TrueNAS host to create a self-signed certificate.

    basicConstraints=CA:FALSE is required: openssl sets CA:TRUE by default for
    self-signed certificates, which causes the middleware to classify the cert
    as a CA and reject it in cert_services_validation.
    """
    if key_type == "RSA":
        # 2048-bit RSA – meets the middleware minimum of 2048 bits.
        ssh(
            f"openssl req -x509 -newkey rsa:2048"
            f" -keyout {key_path} -out {cert_path}"
            f" -sha256 -days 365 -nodes"
            f' -subj "/CN=ftp-tls-test-rsa"'
            f' -addext "basicConstraints=CA:FALSE"'
            f" 2>/dev/null"
        )
    elif key_type == "EC":
        # P-256 (prime256v1) EC key – meets the middleware minimum of 28 bits.
        ssh(
            f"openssl ecparam -genkey -name prime256v1 -noout -out {key_path}"
        )
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
    """If FTP config references *cert_id*, clear it.

    certificate.check_cert_deps raises even when tls=False if the cert ID is
    still stored in ftp_ssltls_certificate_id.  We must set ssltls_certificate
    to None (not just tls to False) to satisfy the dependency check.
    """
    try:
        ftp_config = call("ftp.config")
        if ftp_config.get("ssltls_certificate") == cert_id:
            call("ftp.update", {"tls": False, "ssltls_certificate": None})
    except Exception:
        pass


def _delete_cert_by_name(name: str) -> None:
    """Delete any existing certificate with *name*, ignoring errors.

    Used to remove stale certificates left by a previously failed test run.
    Any FTP reference to the certificate is cleared first so that
    check_cert_deps does not block the deletion.
    """
    existing = call("certificate.query", [["name", "=", name]])
    for cert in existing:
        try:
            _clear_ftp_cert_ref(cert["id"])
            call("certificate.delete", cert["id"], True, job=True)
        except Exception:
            pass


@contextlib.contextmanager
def imported_certificate(name: str, key_type: str):
    """Generate, import and (on exit) delete a self-signed certificate.

    Any stale certificate with the same name is removed before creation so
    that a previously failed run does not block a subsequent run.
    Yields the certificate dict returned by certificate.create.
    """
    cert_path = f"/tmp/ftp-tls-test-{key_type.lower()}-cert.pem"
    key_path = f"/tmp/ftp-tls-test-{key_type.lower()}-key.pem"

    # Pre-clean any certificate left behind by a prior failed run.
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
            # force=True so a 'cert in use' state cannot prevent cleanup.
            try:
                call("certificate.delete", cert["id"], True, job=True)
            except Exception:
                pass
    finally:
        ssh(f"rm -f {cert_path} {key_path}", check=False)


@contextlib.contextmanager
def ftp_tls_enabled(cert_id: int):
    """Enable FTP TLS with *cert_id*, start the service, then restore everything.

    Starting the service causes middlewared to render tls.conf via the mako
    template, which is what we are testing.

    Cleanup is structured in two nested layers so that the FTP configuration
    is always restored even if service.control START/STOP raises:

        ftp.update (apply test config)
        try:
            service.control START
            try:
                yield
            finally:
                service.control STOP   ← inner layer: stop if started
        finally:
            ftp.update (restore)       ← outer layer: always restore config
    """
    original = call("ftp.config")

    # Always restore ssltls_certificate, including None.  Omitting it when the
    # original was None leaves the test cert ID in the DB (tls=False is not
    # enough – check_cert_deps inspects the stored ID regardless of tls state).
    restore = {
        "tls": original["tls"],
        "tls_policy": original["tls_policy"],
        "tls_opt_no_session_reuse_required": original["tls_opt_no_session_reuse_required"],
        "ssltls_certificate": original["ssltls_certificate"],
    }

    call(
        "ftp.update",
        {
            "tls": True,
            "tls_policy": "on",
            "tls_opt_no_session_reuse_required": True,
            "ssltls_certificate": cert_id,
        },
    )

    # Outer finally guarantees config is restored even if START fails.
    try:
        call("service.control", "START", "ftp", {"silent": False}, job=True)
        try:
            yield
        finally:
            call("service.control", "STOP", "ftp", {"silent": False}, job=True)
    finally:
        call("ftp.update", restore)


def parse_tls_conf() -> dict:
    """Read /etc/proftpd/tls.conf from the TrueNAS host and return a mapping
    of ``directive -> value`` (value is *None* for standalone directives).
    """
    content = ssh("cat /etc/proftpd/tls.conf")
    directives = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        key = parts[0]
        value = parts[1].strip('"') if len(parts) > 1 else None
        directives[key] = value
    return directives


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "key_type, expected_cert_dir, expected_key_dir, unexpected_cert_dir, unexpected_key_dir",
    [
        pytest.param(
            "RSA",
            "TLSRSACertificateFile",
            "TLSRSACertificateKeyFile",
            "TLSECCertificateFile",
            "TLSECCertificateKeyFile",
            id="rsa_cert",
        ),
        pytest.param(
            "EC",
            "TLSECCertificateFile",
            "TLSECCertificateKeyFile",
            "TLSRSACertificateFile",
            "TLSRSACertificateKeyFile",
            id="ec_cert",
        ),
    ],
)
def test_ftp_tls_config_directives(
    key_type,
    expected_cert_dir,
    expected_key_dir,
    unexpected_cert_dir,
    unexpected_key_dir,
):
    """tls.conf must use the ProFTPD directives that match the certificate type.

    RSA certificate → TLSRSACertificateFile / TLSRSACertificateKeyFile
    EC  certificate → TLSECCertificateFile  / TLSECCertificateKeyFile
    """
    cert_name = f"ftp-tls-ci-{key_type.lower()}"

    with imported_certificate(cert_name, key_type) as cert:
        # Sanity-check that the middleware correctly identified the key type.
        assert cert["key_type"] == key_type, (
            f"Imported certificate reported key_type={cert['key_type']!r}; "
            f"expected {key_type!r}.  Check that the crypto library parsed the "
            f"certificate correctly."
        )

        with ftp_tls_enabled(cert["id"]):
            directives = parse_tls_conf()

            # The TLS block must have been rendered at all.
            assert "TLSEngine" in directives, (
                "TLSEngine directive not found in tls.conf – the TLS block was "
                "not rendered.  Check that cert_services_validation passes for "
                f"the imported {key_type} certificate (id={cert['id']})."
            )

            # Correct directive for this key type must be present.
            assert expected_cert_dir in directives, (
                f"Expected {expected_cert_dir!r} in tls.conf for a {key_type} "
                f"certificate, but only found: {sorted(directives)}"
            )
            assert expected_key_dir in directives, (
                f"Expected {expected_key_dir!r} in tls.conf for a {key_type} "
                f"certificate, but only found: {sorted(directives)}"
            )

            # Wrong directive for the other key type must NOT be present.
            assert unexpected_cert_dir not in directives, (
                f"Found {unexpected_cert_dir!r} in tls.conf for a {key_type} "
                f"certificate.  The template is not detecting the certificate "
                f"key type correctly."
            )
            assert unexpected_key_dir not in directives, (
                f"Found {unexpected_key_dir!r} in tls.conf for a {key_type} "
                f"certificate.  The template is not detecting the certificate "
                f"key type correctly."
            )

            # The certificate file path must point to the actual cert on disk.
            cert_path_in_conf = directives.get(expected_cert_dir, "")
            assert cert["certificate_path"] in cert_path_in_conf or cert_path_in_conf == cert["certificate_path"], (
                f"{expected_cert_dir} in tls.conf ({cert_path_in_conf!r}) does "
                f"not match the certificate path returned by the API "
                f"({cert['certificate_path']!r})."
            )
