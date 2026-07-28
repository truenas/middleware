import textwrap

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.crypto import (
    CERT_TYPE_CSR,
    acme_registration,
    datastore_certificate,
    generate_csr_pem,
    generate_self_signed_pem,
    imported_certificate,
    ui_certificate,
)
from middlewared.test.integration.utils import call


def test_expired_certificate():
    id_ = call('datastore.insert', 'system.certificate', {
        'certificate': '-----BEGIN CERTIFICATE-----\nMIIDrTCCApWgAwIBAgIELrqsVTANBgkqhkiG9w0BAQsFADCBgDELMAkGA1UEBhMC\nVVMxEjAQBgNVBAoMCWlYc3lzdGVtczESMBAGA1UEAwwJbG9jYWxob3N0MSEwHwYJ\nKoZIhvcNAQkBFhJpbmZvQGl4c3lzdGVtcy5jb20xEjAQBgNVBAgMCVRlbm5lc3Nl\nZTESMBAGA1UEBwwJTWFyeXZpbGxlMB4XDTI0MDEwMTA4MDAyNVoXDTI1MDIwMTA4\nMDAyNVowgYAxCzAJBgNVBAYTAlVTMRIwEAYDVQQKDAlpWHN5c3RlbXMxEjAQBgNV\nBAMMCWxvY2FsaG9zdDEhMB8GCSqGSIb3DQEJARYSaW5mb0BpeHN5c3RlbXMuY29t\nMRIwEAYDVQQIDAlUZW5uZXNzZWUxEjAQBgNVBAcMCU1hcnl2aWxsZTCCASIwDQYJ\nKoZIhvcNAQEBBQADggEPADCCAQoCggEBAKhwebvJ66PPiGgYHdBHTIT1oDAW0T9x\nZMlURfiI8/ld1W28PsBewwM4u6OvljftAdZXIqAzx9cFy+WOrxN5Fz03cdT9dEXl\nTxAjJkC8lh5dVX0SELhwcQ5RVsGrQVZXxCrYt72uP6sDU24GbFt/nmxGzS9cWIjn\nqq+oVQLHZsrUB8LatUxKntVYzAD5X0xO8Sg9eK1gjrQfQEa/XK1XZ3gK0JdlCAk8\n+N+iQUUEy0YC/d/45Vt+8Tvaqr1mZ2cO4yEa1em2vREsLF2AMSfrLbWAjS5TOIqj\nRA4lMEA8Usxqy9hJ4LfYFq/nQeT3gp37u69Vhw7C6ZfjjmuC/owreZ0CAwEAAaMt\nMCswFAYDVR0RBA0wC4IJbG9jYWxob3N0MBMGA1UdJQQMMAoGCCsGAQUFBwMBMA0G\nCSqGSIb3DQEBCwUAA4IBAQCL3BOvsVfQ2a1uZSYl47+JekMVcXZfVBkJeZP66Hbg\nJ5ALTKn5/2bJd4ZOrvysQsk5UlhHGQU0cxTvEeCMck1K8V5LedIaSCJiO+17GAhe\nR6hDCCv1xcSCJNH8KaGR1Hnwx2Tm7AbStViGyFzlnF5CJUZzaxdjUC9E/okZOR8D\nGupwY+wnX8I+oYltcnPPQWKPfuyX22BnWN3qmlx122B5U4VTJ4d+srEEu7V4/u6W\nilwNqSD/tJdMsJDHxR2K/yAVwbfIxg1wHm45EtnO1ir5dRc7KyXL+h/dlqH/86FS\nQKzb/YHDgAVtDWpbtnXL/u+za5d1BFaLjzbZeor/F/yv\n-----END CERTIFICATE-----\n',
        'privatekey': '-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCocHm7yeujz4ho\nGB3QR0yE9aAwFtE/cWTJVEX4iPP5XdVtvD7AXsMDOLujr5Y37QHWVyKgM8fXBcvl\njq8TeRc9N3HU/XRF5U8QIyZAvJYeXVV9EhC4cHEOUVbBq0FWV8Qq2Le9rj+rA1Nu\nBmxbf55sRs0vXFiI56qvqFUCx2bK1AfC2rVMSp7VWMwA+V9MTvEoPXitYI60H0BG\nv1ytV2d4CtCXZQgJPPjfokFFBMtGAv3f+OVbfvE72qq9ZmdnDuMhGtXptr0RLCxd\ngDEn6y21gI0uUziKo0QOJTBAPFLMasvYSeC32Bav50Hk94Kd+7uvVYcOwumX445r\ngv6MK3mdAgMBAAECggEABl8Sy76skiq0fzOCVTGNPG5KG+eRDLROWqs8ZlVP3Tvm\nads4CHDNMZ8AwgVPSlhFvITZQ3QR+Bk5CDrodnUbIu6o+KSJtGcjIXoi5Un857Mi\nG7QGO+PM8vyyqmq+8vQo8HH4KU2hDOf4TO4jRSbDqFbZRhRZKPySYUidxpgiVEO3\nOWuZ+07nsfDS6Qvz3ntKmilsaTCwZJCdjxEk5qlPlSmuipcf3+eFJ3jgudDOMEMd\nz0aBlG2XtpLGnovgaXvrAGpP5X9wPb0etMQV5UZYHpJLF6hh5E6WqaPo+OCWvd7k\nzhDg+XD1f95gncpDn/Qxlierl1YX9IFWZYSpqF5ABQKBgQDZhPrir+J7duZ9wuve\nRBNeh+76qpZXga891DVQ6qMT1m665ymKlXro1fTeL6jRtSUTVnjImcKci5EpoySp\nCYgaSDfYfmfF+VQMtnlsRAv5KrSISDKwQW6Je4gy7sjWE6qkQUIQA4EVJep+Tz8V\nEAouPJlNT/5dWxK0zDl7CgFo4wKBgQDGPMGgiRuDbG/yJCWS9LLWh4UPwttmrH+x\nhL63NGFGQshqwK+4nxbxQ9BFX8KfTZu23OhtalqFnsjQLBIkQMi46NxZPlo/kY8r\nvxv5UBJIK/RucX01tD6lRqcL5p1ZkDRCwOLx0fwIlDk6iBn5C9hnGZbEBQWt8bXN\n3VhDRd2bfwKBgFqNnLBQTnXdqtjCE9Vk+7dH2boq2Am36E9SD5wPAjLY+yH95/JU\nhmV15Mm2h4493iBtyDyinjzzcUwnKbThTfK7C9ypyuPFBzN/p47lySJCoAN4Ivnz\nU2QStEGX3K4aY9ibfjgSbWNzdGp+7SEEm2hiO+POoHMW3fO8bVWGdc3HAoGBAIFE\nvT7iKX7aB2XvDFF4H+alGK/ecRPTCLHJzlPJZGVcxzRV0kCh/WP2xKl4eIFJKnFk\nPGydHcpkcK7PDkV1uW5a6tWHQ3KQiLwOMz+wZzuI7ivW9b8/elpsaCHqkFEHKA0f\nmt32AFPX1DnG5qjwgH06woWwgLOdGuDTpeq4dHohAoGBALERucOuXi3gxHIyugAN\n4z1RE1StU1ywWE4fMnkSMsNFyuNn1FD57X97xGqE0nU4lBDCf0SQjFkSV9MFK7QI\nR9+QKZENVDLCHKrYhZZJcJ+9u/1SXc6gmDtA1JeJyzXfKddvht1W4dkJHjhs1AF1\nLL/21NPlQfDDNTd3SK/VOqfc\n-----END PRIVATE KEY-----\n',
        'name': 'expired_certificate',
        'type': 8,
    }, {'prefix': 'cert_'})
    try:
        alerts = call('alert.run_source', 'CertificateChecks')
        assert len(alerts) == 1
        assert alerts[0]['klass'] == 'CertificateExpired'
    finally:
        call('datastore.delete', 'system.certificate', id_)


# `cryptography` refuses to sign with SHA1, so a certificate with a weak digest
# has to be shipped as a literal. It is valid until 2126 to keep the expiry
# check out of the way of the digest check.
SHA1_CERT = textwrap.dedent("""\
    -----BEGIN CERTIFICATE-----
    MIIDZDCCAkygAwIBAgIUJi7tK0TnHlfba59OkeaZJTeuELQwDQYJKoZIhvcNAQEF
    BQAwNDELMAkGA1UEBhMCVVMxCzAJBgNVBAoMAmlYMRgwFgYDVQQDDA9zaGExLnRl
    c3QubG9jYWwwIBcNMjYwNzI4MDgyMzA2WhgPMjEyNjA3MDQwODIzMDZaMDQxCzAJ
    BgNVBAYTAlVTMQswCQYDVQQKDAJpWDEYMBYGA1UEAwwPc2hhMS50ZXN0LmxvY2Fs
    MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsYmDsb+/QqjUmwyTgMg/
    NVLb9sEfACl+6ICLsvW2224mkwdHcOFUV8fm2wzoDkR/AL2kw4ZMxSTTThH97Cax
    bLuSjcEoT0/ZixiimSlyis6iU84wsS+dgKq+jm1LtNa+YHK81Cvd64HJFHSOSzoc
    KPb2/wEwbxjtN6bYh2lbfHkKiPRONeX1mxG6Jd9armKgRJOBl1XDOApNu4NzvHA8
    OWzHtAaL/UA0ENPwVofUK8v/7CoZqW1JitSqHIgJRpOxzmYcWspZzXfbnPG87IGj
    HXBLGUcW23T1Ip38+H2NxW9Ot7VTu1gzXhyvaD/A0VEysM4InVV/nlNrLoYKqk/z
    VwIDAQABo2wwajAdBgNVHQ4EFgQU5V04Z24Oq6JUYSpcoWjGMtaLAEAwHwYDVR0j
    BBgwFoAU5V04Z24Oq6JUYSpcoWjGMtaLAEAwGgYDVR0RBBMwEYIPc2hhMS50ZXN0
    LmxvY2FsMAwGA1UdEwEB/wQCMAAwDQYJKoZIhvcNAQEFBQADggEBAJFIk/zTzSdv
    KnEAvMZBHRw0yonaRV2A/ie0RhRuQdLgB2fanca9OoAyaPpmVHj7p6bhRa0dUmV6
    E84HFWGANwjFniqqmAAdLgQiKn/AKUQpqkyXhiVPlsr+gP0/BqmRtcdLyaU28pTb
    04CBAzBKi0Zjz+n1l9KEm0UPyiXrYN4qfwa9RBAFc9z7r/hnSFYKcZsHeLI0Orsu
    mm68Qgz4/Voy+nByg/aMeqJobhfuhcX3Vxc4kKkvfIOSPIdtIndWdN61RSsyVwvb
    XONh6TcQ817fXvmufjp1airOIjTg64+YPInDGVmI9lPKmGMMc+Rd6n/6yLxEuELN
    05vkmzzcYgs=
    -----END CERTIFICATE-----
""")
SHA1_KEY = textwrap.dedent("""\
    -----BEGIN PRIVATE KEY-----
    MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCxiYOxv79CqNSb
    DJOAyD81Utv2wR8AKX7ogIuy9bbbbiaTB0dw4VRXx+bbDOgORH8AvaTDhkzFJNNO
    Ef3sJrFsu5KNwShPT9mLGKKZKXKKzqJTzjCxL52Aqr6ObUu01r5gcrzUK93rgckU
    dI5LOhwo9vb/ATBvGO03ptiHaVt8eQqI9E415fWbEbol31quYqBEk4GXVcM4Ck27
    g3O8cDw5bMe0Bov9QDQQ0/BWh9Qry//sKhmpbUmK1KociAlGk7HOZhxaylnNd9uc
    8bzsgaMdcEsZRxbbdPUinfz4fY3Fb063tVO7WDNeHK9oP8DRUTKwzgidVX+eU2su
    hgqqT/NXAgMBAAECggEAFwKJrQn7Efqrw4S3wWMyvgiFNdAF4pF+P0gZ0xIBpyL5
    oOi6m6i4s7/W7eEYWnEKPOBXcHgBjzOcp2uxi1/gcwVEk1bLkKv6uApzWIKEs/Tg
    GRiKOwy+zyRSGkeUHlYOypVUX/NnidSCaUJKBvn7GFwZ2yceTeffJu1a9wHyt4kI
    xm2uJd4lMQjFoTzE7rLjMJeobEiKLFBxk0EiOSmV+60j5MIfDRRxjzPyFxR71MI0
    vk7pmGPHkGrhYcyTfOR8LuzdJoHnEkMzhsvUiwgVWBoBHNzi2SsXSWU+yi/xhBLV
    8sbefm8HMwFYsfZbVu3/iluW8rNEGAizSPYrLNPw0QKBgQD0/pxTYBvSgJk3JGsc
    ebThJKowteTLWXzgB7A7ihpgjRamShOVocPbNkvL3HorKAoBM9sXaS3EqaTXl+o0
    oZk0EiPE8eKTE6Y5O1gHDLWEsGoiMiHCxAEWAlkkxDkt4qCcDk3nGq+gJK/9HadK
    oK7Cwvsd/7Ri67qX+BdU+7D7swKBgQC5gygpgPhHLJ2QBoFg4a55KGKQebwAGgcx
    bwbVRZHcPOi9PDKfGWBMcnJnS0KtYKUTnvEourD2njRo1JtCm3SU5lyezDYmcS0F
    mUGaqbWQSP9fP1UTxgTi6K09fPCoVuRWRHlouwOqfZUXdVxyLEETB7WVAzDpPdCa
    QqADSjmHzQKBgFEG4Fbm42zEYWgOYGqDiiIoSS1hCzGCAD3r7QpUC5NBNmt69m03
    mhonI/xhh/o7/MsXBnAAtkVjwgQX1zre81d4ZGIficsQ5ZnqGZwDRQmEeyWiJO5Q
    evd3gVoal7qoSGw0gulbNxik6ZuyMgEJkaMSb5ElX9iTlBvsznKp54fnAoGAKuVK
    +h3aSwrj/BOlAvPsVhOihum/MP7Tvvh/Sf1mNtjWsDslMWi6vbKRBZV/e3uncBwG
    g3Z3yO7YC41twT8U/AEwVX++3bC5ylufsdWgKBbZBfss/v+Azb8jn94t/57n+ZKn
    yDHGLTwQp3X5xGS7P10+/Y/ZVXV3sNPLEDevidkCgYEAzC3rEwHR5oX6xI2L7KRV
    2SvAflJIs085R+cjqXmyRILvSf1q3E9b3ulHkKAQixH6YpKL7zTQ+xSaIuQ+7hYs
    3j9WB/tvu+kJA4C6knQIR97mAle35vYmUJjkDqAkYAp+P3W7gLdo7ctDf9ENyKEa
    1tBSldeEQcI34caxxZ/r8v4=
    -----END PRIVATE KEY-----
""")

MALFORMED_CERT = "-----BEGIN CERTIFICATE-----\nZ2FyYmFnZQ==\n-----END CERTIFICATE-----\n"
MALFORMED_KEY = "-----BEGIN PRIVATE KEY-----\nZ2FyYmFnZQ==\n-----END PRIVATE KEY-----\n"


def assert_service_validation_error(cert_id, expected):
    """`certificate.cert_services_validation` raises the collected problems.

    It is not a job, so the client re-raises the server-side exception class
    rather than the API client's own `ValidationErrors`.
    """
    with pytest.raises(ValidationErrors) as ve:
        call("certificate.cert_services_validation", cert_id, "test_schema")
    assert any(expected in e.errmsg for e in ve.value.errors), ve.value.errors


def test_cert_services_validation_unknown_certificate():
    assert_service_validation_error(999999, "No Certificate found with the provided id")


def test_cert_services_validation_healthy_certificate():
    cert_pem, key_pem = generate_self_signed_pem(common_name="healthy.test.local")
    with imported_certificate("healthy_cert", cert_pem, key_pem) as cert:
        assert call("certificate.cert_services_validation", cert["id"], "test_schema") is None


def test_cert_services_validation_rejects_csr():
    csr_pem, key_pem = generate_csr_pem("csr.health.local")
    with datastore_certificate(
        "health_csr", cert_type=CERT_TYPE_CSR, CSR=csr_pem, privatekey=key_pem
    ) as csr:
        assert_service_validation_error(csr["id"], "not a CSR or CA")


def test_cert_services_validation_rejects_ca():
    cert_pem, key_pem = generate_self_signed_pem(common_name="ca.health.local", ca=True)
    with imported_certificate("health_ca", cert_pem, key_pem) as cert:
        assert_service_validation_error(cert["id"], "not a CSR or CA")


def test_cert_services_validation_malformed_certificate():
    with datastore_certificate("health_malformed", certificate=MALFORMED_CERT) as cert:
        assert_service_validation_error(cert["id"], "certificate is malformed")


def test_cert_services_validation_without_private_key():
    cert_pem, _ = generate_self_signed_pem(common_name="nokey.health.local")
    with datastore_certificate("health_no_key", certificate=cert_pem) as cert:
        assert_service_validation_error(cert["id"], "does not have a private key")


def test_cert_services_validation_unparseable_private_key():
    cert_pem, _ = generate_self_signed_pem(common_name="badkey.health.local")
    with datastore_certificate(
        "health_bad_key", certificate=cert_pem, privatekey=MALFORMED_KEY
    ) as cert:
        assert_service_validation_error(cert["id"], "Failed to parse certificate's private key")


def test_cert_services_validation_key_too_short():
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    cert_pem, key_pem = generate_self_signed_pem(common_name="short.health.local", key=key)
    with datastore_certificate(
        "health_short_key", certificate=cert_pem, privatekey=key_pem
    ) as cert:
        assert_service_validation_error(cert["id"], "private key size is less than 2048 bits")


def test_cert_services_validation_expired_certificate():
    cert_pem, key_pem = generate_self_signed_pem(common_name="expired.health.local", expired=True)
    with datastore_certificate(
        "health_expired", certificate=cert_pem, privatekey=key_pem
    ) as cert:
        assert_service_validation_error(cert["id"], "has expired")


def test_cert_services_validation_weak_digest_algorithm():
    with datastore_certificate(
        "health_sha1", certificate=SHA1_CERT, privatekey=SHA1_KEY
    ) as cert:
        assert cert["digest_algorithm"] == "SHA1", cert
        assert_service_validation_error(cert["id"], "at least 112 security bits")


def test_cert_services_validation_truenas_connect_certificate():
    # Certificates named with the TrueNAS Connect prefix are reserved for that
    # service unless they are the configured UI certificate.
    cert_pem, key_pem = generate_self_signed_pem(common_name="tnc.health.local")
    with imported_certificate("truenas_connect_reserved", cert_pem, key_pem) as cert:
        assert_service_validation_error(cert["id"], "reserved for TrueNAS Connect service")


def test_renew_certs_skips_healthy_certificates():
    # The UI certificate and the TrueNAS Connect certificate are always
    # considered for renewal, but neither is close enough to expiry to renew.
    cert_pem, key_pem = generate_self_signed_pem(common_name="tnc.renew.local")
    with imported_certificate("renew_tnc", cert_pem, key_pem) as cert:
        call("datastore.update", "truenas_connect", 1, {"certificate": cert["id"]})
        try:
            call("certificate.renew_certs", job=True)
            assert call("certificate.query", [["id", "=", cert["id"]]], {"get": True})["expired"] is False
        finally:
            call("datastore.update", "truenas_connect", 1, {"certificate": None})


def test_renew_certs_without_system_certificates():
    # A UI certificate that was not generated by us is left alone, which leaves
    # only ACME certificates to consider — and one that could not be parsed has
    # no expiry date to compare against.
    cert_pem, key_pem = generate_self_signed_pem(common_name="third.party.local", organization="Acme Corp")
    with imported_certificate("renew_third_party", cert_pem, key_pem) as cert:
        with acme_registration() as registration_id:
            with datastore_certificate(
                "renew_unparseable_acme", certificate=MALFORMED_CERT, acme=registration_id
            ) as acme_cert:
                with ui_certificate(cert["id"]):
                    call("certificate.renew_certs", job=True)
                assert call("certificate.query", [["id", "=", acme_cert["id"]]], {"get": True})["until"] is None


def test_renew_certs_renews_expired_system_certificate():
    # A self-signed certificate we generated ourselves and that is now expired
    # gets regenerated in place.
    cert_pem, key_pem = generate_self_signed_pem(
        common_name="localhost", organization="iXsystems", san=["localhost"], expired=True
    )
    with datastore_certificate(
        "renew_expired_ui", certificate=cert_pem, privatekey=key_pem
    ) as cert:
        assert cert["expired"] is True, cert
        with ui_certificate(cert["id"]):
            call("certificate.renew_certs", job=True)

        renewed = call("certificate.query", [["id", "=", cert["id"]]], {"get": True})
        assert renewed["expired"] is False, renewed
        assert renewed["until"] != cert["until"], renewed


def test_cert_services_validation_truenas_connect_certificate_used_by_ui():
    # The reservation does not apply when the certificate is the one the UI is
    # already configured with.
    cert_pem, key_pem = generate_self_signed_pem(common_name="tnc.ui.local")
    with imported_certificate("truenas_connect_ui", cert_pem, key_pem) as cert:
        with ui_certificate(cert["id"]):
            assert call("certificate.cert_services_validation", cert["id"], "test_schema") is None


def test_renew_certs_without_ui_certificate():
    with ui_certificate(None):
        assert call("system.general.config")["ui_certificate"] is None
        call("certificate.renew_certs", job=True)
