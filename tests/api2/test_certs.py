import textwrap

import pytest
from cryptography.hazmat.primitives.asymmetric import dsa, ed448, ed25519

from middlewared.test.integration.assets.crypto import (
    CERT_TYPE_CSR,
    certificate_signing_request,
    datastore_certificate,
    generate_self_signed_pem,
)
from middlewared.test.integration.utils import call, ssh
from truenas_api_client import ValidationErrors


def test_creating_csr():
    with certificate_signing_request("csr_test") as csr:
        assert csr["cert_type_CSR"] is True, csr


def test_created_certs_exist_on_filesystem():
    with certificate_signing_request("csr_test"):
        assert get_cert_current_files() == get_cert_expected_files()


def test_deleted_certs_dont_exist_on_filesystem():
    with certificate_signing_request("csr_test2"):
        pass
    assert get_cert_current_files() == get_cert_expected_files()


def get_cert_expected_files():
    expected_files = set()
    for cert in call("certificate.query"):
        if cert["chain_list"]:
            expected_files.add(cert["certificate_path"])
        if cert["privatekey"]:
            expected_files.add(cert["privatekey_path"])
        if cert["cert_type_CSR"]:
            expected_files.add(cert["csr_path"])
    return expected_files


def get_cert_current_files():
    return {f["path"] for f in call("filesystem.listdir", "/etc/certificates")}


@pytest.mark.parametrize(
    "certificate,private_key,should_work",
    [
        (
            textwrap.dedent("""\
            -----BEGIN CERTIFICATE-----
            MIIEDTCCAvWgAwIBAgIEAKWUWTANBgkqhkiG9w0BAQsFADBVMQswCQYDVQQGEwJV
            UzEMMAoGA1UECAwDdXNhMRMwEQYDVQQHDApjYWxpZm9ybmlhMQswCQYDVQQKDAJs
            bTEWMBQGCSqGSIb3DQEJARYHYUBiLmNvbTAeFw0yMzA0MDYxNjQyMTJaFw0yNDA1
            MDcxNjQyMTJaME4xCzAJBgNVBAYTAlVTMQwwCgYDVQQIDAN1c2ExDDAKBgNVBAcM
            A3VzYTELMAkGA1UECgwCbG0xFjAUBgkqhkiG9w0BCQEWB2FAYy5jb20wggEiMA0G
            CSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCtvPEA2x3/jp0riSdgb7TqB9uAobzt
            tYbW9E0+WLqf3sLJJ4F4Iq0AI1YYMtOOwcjmvC52eSaqxoGcY4G2J+RgQNR8b8lk
            m38vRYQA2SkDCtEQFkLiCrkr5g20xh89gCLEr9c5x45p8Pl7q2LmE6wVIVjWqTSi
            Yo4TMD8Nb5LN3vPeM7+fwV7FZDH7PJ4AT1/kTJjhkK0wiOGeTLEW5wiSYO8QMD0r
            JHfzAp8UPFsVK8InZTjLS4VJgI0OlG2Von7Nv7Wtxsg5hi7dkLu2tawHE8DD97O5
            zhVTZHzBiDF1mrjR3+6RWgn8iF6353UV9hbyPYz51UiCEYHBwFtqQaBlAgMBAAGj
            geswgegwDgYDVR0RBAcwBYIDYWJjMB0GA1UdDgQWBBSRzlS66ts6rhuCN+4VK2x7
            8E+n1zAMBgNVHRMBAf8EAjAAMIGABgNVHSMEeTB3gBR1fZ31S5XHrijsT/C9fzbB
            aqrg5qFZpFcwVTELMAkGA1UEBhMCVVMxDDAKBgNVBAgMA3VzYTETMBEGA1UEBwwK
            Y2FsaWZvcm5pYTELMAkGA1UECgwCbG0xFjAUBgkqhkiG9w0BCQEWB2FAYi5jb22C
            BACllFgwFgYDVR0lAQH/BAwwCgYIKwYBBQUHAwIwDgYDVR0PAQH/BAQDAgOIMA0G
            CSqGSIb3DQEBCwUAA4IBAQA7UwYNr6gspgRcCGwzl5RUAL/N3NXv3rcgTPF405s5
            OXKDPAxWSulzt/jqAesYvI27koOsGj0sDsSRLRdmj4HG91Xantnv5rxGqdYHEDPo
            j8oo1HQv8vqhDcKUJOKH5j5cWO+W75CpAHuMfgxKJ9WdxPSNpKZoOKIMd2hwd4ng
            2+ulgfvVKcE4PM4YSrtW4qoAoz/+gyfwSoIAQJ0VOuEwL+QFJ8Ud1aJaJRkLD39P
            uLEje++rBbfIX9VPCRS/c3gYAOHu66LYI3toTomY8U3YYiQk8bC3Rp9uAjmgI3br
            4DHLwRTEUbOL8CdNcGb1qvO8xBSRzjMIZM8QJHSyYNcM
            -----END CERTIFICATE-----
        """),
            textwrap.dedent("""\
            -----BEGIN PRIVATE KEY-----
            MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCtvPEA2x3/jp0r
            iSdgb7TqB9uAobzttYbW9E0+WLqf3sLJJ4F4Iq0AI1YYMtOOwcjmvC52eSaqxoGc
            Y4G2J+RgQNR8b8lkm38vRYQA2SkDCtEQFkLiCrkr5g20xh89gCLEr9c5x45p8Pl7
            q2LmE6wVIVjWqTSiYo4TMD8Nb5LN3vPeM7+fwV7FZDH7PJ4AT1/kTJjhkK0wiOGe
            TLEW5wiSYO8QMD0rJHfzAp8UPFsVK8InZTjLS4VJgI0OlG2Von7Nv7Wtxsg5hi7d
            kLu2tawHE8DD97O5zhVTZHzBiDF1mrjR3+6RWgn8iF6353UV9hbyPYz51UiCEYHB
            wFtqQaBlAgMBAAECggEAFNc827rtIspDPUUzFYTg4U/2+zurk6I6Xg+pMmjnXiUV
            HZchFz2lngYfHkD+krnZNSBuvGR1CHhOdOmU1jp70TYFpzWrpWdnvs5qcsWZ/1Tt
            Vi4tcLsTkloC2+QGPFTiFtD3EuXGxhuTecvJzcqfUluRMhLTDwWegFvBvIVdSVeZ
            9XFDZF9O748tdt2PhYcL2L/xDz4sIz89ek4P1v4raB52rcleIduqMat29crVR3ex
            VsZK3PLW6HCquUQvdvjLblfzjDS1pqcpIiSsYCrP0eEEKrrg44V8VjcPxXIg4GAE
            ioDOpi9vO/3xyxYxXBtlD2o6c9kZUrp+xxx9jztdIQKBgQDo8witC33Z7Rd6dLm9
            zgN/wZ2lWqE927fXZBExKjCXZ+A3N58One0TR2qI9S+BRVc2KOCWFGUjnHbx1PfE
            xU1UNDY+ir9Lqk+rzhyEk4vst/IwhyovmAhL5fONqlfxB+l29cUh6JIYMtqaWYvj
            AbmS5YhZRMa3kI/BtCTRJtPecQKBgQC+7f57XWt7HNe7FvrDTz5M8AmQ7y487NxZ
            OcZ1+YKJ57PVY7G7Ye3xqRTd05L6h1P1eCO0gLDiSy5VOz47uFdNcD/9Ia+Ng2oq
            P8TC36b86dz3ZDhBm4AB3shaD/JBjUQ0NwLosmrMaDF+lVu8NPA60eeQ70/RgbSA
            KNrOUH1DNQKBgQDicOzsGZGat6fs925enNY16CWwSOsYUG7ix3kWy6Y0Z1tDEaRh
            9w4vgWqD+6LUDG18TjwSZ3zxIvVUmurGsew7gA2Cuii+Cq4rmc2K6kpIL38TwTA2
            15io/rzD5uRZfpFpe/rGvWbWcwigpY8fedvEea8S55IrejDj4JMxZIbrYQKBgQCG
            Ke68+XRhWm8thIRJYhHBNptCQRAYt8hO2o5esCnOhgaUWC24IqR1P/7tsZKCgT26
            K+XLHPMu0O2J7stYY7zVKZ+NXHJj2ohrj8vPtCE/b4ZaQQ5W69ITfl0DDFmLPp1C
            o7Vjlpv9bun4rTN9GSYF7yHtcnyAF8iilhLLDzw2UQKBgQC4FzI6/P2HcUNzf+/m
            AThk8+4V35gOSxn3uk48CXNStcCoLMEeXM69SGYq8GaGU/piaog9D8RvF4yMAnnL
            wNpy8J/4ldluyidX61N0dMS+NL4l4TPjTvOY22KzjwfnBoqzg+93Mt//M4HfR/ka
            3EWl5VmzbuEeytrcH3uHAUpkKg==
            -----END PRIVATE KEY-----
        """),
            True,
        ),
        (
            textwrap.dedent("""\
           -----BEGIN CERTIFICATE-----
           MIIEDTCCAvWgAwIBAgIEAKWUWTANBgkqhkiG9w0BAQsFADBVMQswCQYDVQQGEwJV
           UzEMMAoGA1UECAwDdXNhMRMwEQYDVQQHDApjYWxpZm9ybmlhMQswCQYDVQQKDAJs
           bTEWMBQGCSqGSIb3DQEJARYHYUBiLmNvbTAeFw0yMzA0MDYxNjQyMTJaFw0yNDA1
           MDcxNjQyMTJaME4xCzAJBgNVBAYTAlVTMQwwCgYDVQQIDAN1c2ExDDAKBgNVBAcM
           A3VzYTELMAkGA1UECgwCbG0xFjAUBgkqhkiG9w0BCQEWB2FAYy5jb20wggEiMA0G
           CSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCtvPEA2x3/jp0riSdgb7TqB9uAobzt
           tYbW9E0+WLqf3sLJJ4F4Iq0AI1YYMtOOwcjmvC52eSaqxoGcY4G2J+RgQNR8b8lk
           m38vRYQA2SkDCtEQFkLiCrkr5g20xh89gCLEr9c5x45p8Pl7q2LmE6wVIVjWqTSi
           Yo4TMD8Nb5LN3vPeM7+fwV7FZDH7PJ4AT1/kTJjhkK0wiOGeTLEW5wiSYO8QMD0r
           JHfzAp8UPFsVK8InZTjLS4VJgI0OlG2Von7Nv7Wtxsg5hi7dkLu2tawHE8DD97O5
           zhVTZHzBiDF1mrjR3+6RWgn8iF6353UV9hbyPYz51UiCEYHBwFtqQaBlAgMBAAGj
           geswgegwDgYDVR0RBAcwBYIDYWJjMB0GA1UdDgQWBBSRzlS66ts6rhuCN+4VK2x7
           8E+n1zAMBgNVHRMBAf8EAjAAMIGABgNVHSMEeTB3gBR1fZ31S5XHrijsT/C9fzbB
           aqrg5qFZpFcwVTELMAkGA1UEBhMCVVMxDDAKBgNVBAgMA3VzYTETMBEGA1UEBwwK
           Y2FsaWZvcm5pYTELMAkGA1UECgwCbG0xFjAUBgkqhkiG9w0BCQEWB2FAYi5jb22C
           BACllFgwFgYDVR0lAQH/BAwwCgYIKwYBBQUHAwIwDgYDVR0PAQH/BAQDAgOIMA0G
           CSqGSIb3DQEBCwUAA4IBAQA7UwYNr6gspgRcCGwzl5RUAL/N3NXv3rcgTPF405s5
           OXKDPAxWSulzt/jqAesYvI27koOsGj0sDsSRLRdmj4HG91Xantnv5rxGqdYHEDPo
           j8oo1HQv8vqhDcKUJOKH5j5cWO+W75CpAHuMfgxKJ9WdxPSNpKZoOKIMd2hwd4ng
           2+ulgfvVKcE4PM4YSrtW4qoAoz/+gyfwSoIAQJ0VOuEwL+QFJ8Ud1aJaJRkLD39P
           uLEje++rBbfIX9VPCRS/c3gYAOHu66LYI3toTomY8U3YYiQk8bC3Rp9uAjmgI3br
           4DHLwRTEUbOL8CdNcGb1qvO8xBSRzjMIZM8QJHSyYNcM
           -----END CERTIFICATE-----
        """),
            textwrap.dedent("""\
            -----BEGIN PRIVATE KEY-----
            MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDVMPccUqq6jd8h
            h0ybrwRkvK+pvOJze00IK7F6A8RRyCwDL2Yc0GpWR5ecY+jBiZ1n+TfKfaybdKR0
            0hhFFuU74JTsUk298hI1GVBNvwbimgraQciWjg0wDjHAN7AFZL8Jb/Tn7/DZlmn+
            TgqdPaFIeD4XnLX6zwrc4VemKYDDcdr5JyDVCt3ZtqTEbbtxQ4WvZbtCxlzlkyJu
            xwdmGyCvjkQri55+FaejvnPCUzJSOK28jShBuZCIS3lR7HCcAS4cc05TTrWSZr+i
            brLISVEz1XASc0pKz8QGMuz5Hk5uNRLl4JGmWZrSV9lqtFYP9hatpLi5mnhWpgYi
            Q0IXvNUXAgMBAAECggEAdbgf+0e6dmC4gO8Q4jZ2GpoF9ZgTAulm08gsq89ArFf3
            1ZpqrCZ5UUMe+IBCmfu/KxZ2NB3JHd3+oXMRa7UEx1dvZD7eJrBwVVmw+f0tdBrT
            O0lv1ZKCvbJYzmbxj0jeI/vqI9heCggAZyf4vHK3iCi9QJSL9/4zZVwY5eus6j4G
            RCMXW8ZqiKX3GLtCjPmZilYQHNDbsfAbqy75AsG81fgaKkYkJS29rte9R34BajZs
            OFm+y6nIe6zsf0vhn/yPVN4Yhuu/WhkvqouR2NhSF7ulXckuR/ef55GPpbRcpSOj
            VUkwJL3wsHPozvmcks/TnZbqj0u7XBGjZ2VK8sF+gQKBgQDsJGMeeaua5pOITVHk
            reHaxy4tLs1+98++L9SffBbsQcCu4OdgMBizCXuUw9bHlMx19B/B56cJst239li3
            dHfC/mF4/8em5XOx97FyC0rF02qYCPXViTrTSovSEWHuM/ChmhaRlZdp5F4EBMp7
            ELdf4OBCHGz47UCLQF75/FPtJwKBgQDnHn9HuFepY+yV1sNcPKj1GfciaseKzTk1
            Iw5VVtqyS2p8vdXNUiJmaF0245S3phRBL6PDhdfd3SwMmNYvhTYsqBc6ZRHO4b9J
            SjmHct63286NuEn0piYaa3MZ8sV/xI0a5leAdkzyqPTCcn0HlvDL0HTV34umdmfj
            kqC4jsWukQKBgC48cavl5tPNkdV+TiqYYUCU/1WZdGMH4oU6mEch5NsdhLy5DJSo
            1i04DhpyvfsWB3KQ+ibdVLdxbjg24+gHxetII42th0oGY0DVXskVrO5PFu/t0TSe
            SgZU8kuPW71oLhV2NjULNTpmnIHs7jhqbX04arCHIE8dJSYe1HneDhDBAoGBALTk
            4txgxYQYaNFykd/8voVwuETg7KOQM0mK0aor2+qXKpbOAqy8r54V63eNsxX20H2g
            6v2bIbVOai7F5Ua2bguP2PZkqwaRHKYhiVuhpf6j9UxpRMFO1h3xodpacQiq74Jx
            bWVnspxvb3tOHtw04O21j+ziFizJGlE9r7wkS0dxAoGAeq/Ecb+nJp/Ce4h5US1O
            4rruiLLYMkcFGmhSMcQ+lVbGOn4eSpqrGWn888Db2oiu7mv+u0TK9ViXwHkfp4FP
            Hnm0S8e25py1Lj+bk1tH0ku1I8qcAtihYBtSwPGj+66Qyr8KOlxZP2Scvcqu+zBc
            cyhsrrlRc3Gky9L5gtdxdeo=
            -----END PRIVATE KEY-----
        """),
            False,
        ),
        (
            textwrap.dedent("""\
           -----BEGIN CERTIFICATE-----
           ntnv5rxGqdYHEDPo
           j8oo1HQv8vqhDcKUJOKH5j5cWO+W75CpAHuMfgxKJ9WdxPSNpKZoOKIMd2hwd4ng
           2+ulgfvVKcE4PM4YSrtW4qoAoz/+gyfwSoIAQJ0VOuEwL+QFJ8Ud1aJaJRkLD39P
           uLEje++rBbfIX9VPCRS/c3gYAOHu66LYI3toTomY8U3YYiQk8bC3Rp9uAjmgI3br
           4DHLwRTEUbOL8CdNcGb1qvO8xBSRzjMIZM8QJHSyYNcM
           -----END CERTIFICATE-----
        """),
            textwrap.dedent("""\
            -----BEGIN PRIVATE KEY-----
            MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDVMPccUqq6jd8h
            h0ybrwRkvK+pvOJze00IK7F6A8RRyCwDL2Yc0GpWR5ecY+jBiZ1n+TfKfaybdKR0
            0hhFFuU74JTsUk298hI1GVBNvwbimgraQciWjg0wDjHAN7AFZL8Jb/Tn7/DZlmn+
            TgqdPaFIeD4XnLX6zwrc4VemKYDDcdr5JyDVCt3ZtqTEbbtxQ4WvZbtCxlzlkyJu
            xwdmGyCvjkQri55+FaejvnPCUzJSOK28jShBuZCIS3lR7HCcAS4cc05TTrWSZr+i
            brLISVEz1XASc0pKz8QGMuz5Hk5uNRLl4JGmWZrSV9lqtFYP9hatpLi5mnhWpgYi
            Q0IXvNUXAgMBAAECggEAdbgf+0e6dmC4gO8Q4jZ2GpoF9ZgTAulm08gsq89ArFf3
            1ZpqrCZ5UUMe+IBCmfu/KxZ2NB3JHd3+oXMRa7UEx1dvZD7eJrBwVVmw+f0tdBrT
            O0lv1ZKCvbJYzmbxj0jeI/vqI9heCggAZyf4vHK3iCi9QJSL9/4zZVwY5eus6j4G
            RCMXW8ZqiKX3GLtCjPmZilYQHNDbsfAbqy75AsG81fgaKkYkJS29rte9R34BajZs
            OFm+y6nIe6zsf0vhn/yPVN4Yhuu/WhkvqouR2NhSF7ulXckuR/ef55GPpbRcpSOj
            VUkwJL3wsHPozvmcks/TnZbqj0u7XBGjZ2VK8sF+gQKBgQDsJGMeeaua5pOITVHk
            reHaxy4tLs1+98++L9SffBbsQcCu4OdgMBizCXuUw9bHlMx19B/B56cJst239li3
            dHfC/mF4/8em5XOx97FyC0rF02qYCPXViTrTSovSEWHuM/ChmhaRlZdp5F4EBMp7
            ELdf4OBCHGz47UCLQF75/FPtJwKBgQDnHn9HuFepY+yV1sNcPKj1GfciaseKzTk1
            Iw5VVtqyS2p8vdXNUiJmaF0245S3phRBL6PDhdfd3SwMmNYvhTYsqBc6ZRHO4b9J
            SjmHct63286NuEn0piYaa3MZ8sV/xI0a5leAdkzyqPTCcn0HlvDL0HTV34umdmfj
            kqC4jsWukQKBgC48cavl5tPNkdV+TiqYYUCU/1WZdGMH4oU6mEch5NsdhLy5DJSo
            1i04DhpyvfsWB3KQ+ibdVLdxbjg24+gHxetII42th0oGY0DVXskVrO5PFu/t0TSe
            SgZU8kuPW71oLhV2NjULNTpmnIHs7jhqbX04arCHIE8dJSYe1HneDhDBAoGBALTk
            4txgxYQYaNFykd/8voVwuETg7KOQM0mK0aor2+qXKpbOAqy8r54V63eNsxX20H2g
            6v2bIbVOai7F5Ua2bguP2PZkqwaRHKYhiVuhpf6j9UxpRMFO1h3xodpacQiq74Jx
            bWVnspxvb3tOHtw04O21j+ziFizJGlE9r7wkS0dxAoGAeq/Ecb+nJp/Ce4h5US1O
            4rruiLLYMkcFGmhSMcQ+lVbGOn4eSpqrGWn888Db2oiu7mv+u0TK9ViXwHkfp4FP
            Hnm0S8e25py1Lj+bk1tH0ku1I8qcAtihYBtSwPGj+66Qyr8KOlxZP2Scvcqu+zBc
            cyhsrrlRc3Gky9L5gtdxdeo=
            -----END PRIVATE KEY-----
        """),
            False,
        ),
    ],
    ids=["valid_cert", "invalid_cert", "invalid_cert"],
)
def test_importing_certificate_validation(certificate, private_key, should_work):
    payload = {
        "name": "test-cert",
        "create_type": "CERTIFICATE_CREATE_IMPORTED",
        "certificate": certificate,
        "privatekey": private_key,
    }
    if should_work:
        cert = call("certificate.create", payload, job=True)
        try:
            assert cert["parsed"] is True, cert
        finally:
            call("certificate.delete", cert["id"], job=True)
    else:
        with pytest.raises(ValidationErrors):
            call("certificate.create", payload, job=True)


# Material that satisfies the PEM regex but cannot be parsed. It can only be put
# in front of the query code by writing it straight to the datastore.
MALFORMED_CERT = "-----BEGIN CERTIFICATE-----\nZ2FyYmFnZQ==\n-----END CERTIFICATE-----\n"
MALFORMED_KEY = "-----BEGIN PRIVATE KEY-----\nZ2FyYmFnZQ==\n-----END PRIVATE KEY-----\n"
MALFORMED_CSR = "-----BEGIN CERTIFICATE REQUEST-----\nZ2FyYmFnZQ==\n-----END CERTIFICATE REQUEST-----\n"


def test_query_unparseable_certificate():
    with datastore_certificate(
        "unparseable_cert", certificate=MALFORMED_CERT, privatekey=MALFORMED_KEY
    ) as cert:
        assert cert["parsed"] is False, cert
        assert cert["chain_list"] == [], cert
        # Everything derived from the certificate is normalized away.
        assert cert["fingerprint"] is None, cert
        assert cert["until"] is None, cert
        assert cert["extensions"] == {}, cert
        # ... and so is everything derived from the unreadable private key.
        assert cert["key_length"] is None, cert
        assert cert["key_type"] is None, cert


def test_query_unparseable_csr():
    with datastore_certificate(
        "unparseable_csr", cert_type=CERT_TYPE_CSR, CSR=MALFORMED_CSR
    ) as csr:
        assert csr["cert_type_CSR"] is True, csr
        assert csr["parsed"] is False, csr
        assert csr["common"] is None, csr


@pytest.mark.parametrize(
    "key_factory,expected_key_type,expected_key_length",
    [
        (lambda: dsa.generate_private_key(key_size=2048), "DSA", 2048),
        (ed448.Ed448PrivateKey.generate, "OTHER", None),
        (ed25519.Ed25519PrivateKey.generate, "EC", 32),
    ],
    ids=["dsa", "ed448", "ed25519"],
)
def test_query_reports_key_type(key_factory, expected_key_type, expected_key_length):
    # certificate.create only ever produces RSA/EC keys, so the remaining
    # branches of the key introspection are reachable only via the datastore.
    cert_pem, key_pem = generate_self_signed_pem(common_name="keytype.test.local", key=key_factory())
    with datastore_certificate("key_type_cert", certificate=cert_pem, privatekey=key_pem) as cert:
        assert cert["parsed"] is True, cert
        assert cert["key_type"] == expected_key_type, cert
        assert cert["key_length"] == expected_key_length, cert


def test_redeploy_cert_attachments():
    # The UI certificate always has at least the UI service attached to it.
    ui_cert_id = call("system.general.config")["ui_certificate"]
    assert call("certificate.get_attachments", ui_cert_id)
    call("certificate.redeploy_cert_attachments", ui_cert_id)


def test_dhparam_setup():
    ssh("cp -a /data/dhparam.pem /data/dhparam.pem.bak")
    try:
        ssh("truncate -s 0 /data/dhparam.pem")
        call("certificate.dhparam_setup", job=True)
        size, mode = ssh("stat -c '%s %a' /data/dhparam.pem").split()
        assert int(size) > 0
        assert mode == "600"

        # An existing non-empty file is left alone.
        before = ssh("sha256sum /data/dhparam.pem")
        call("certificate.dhparam_setup", job=True)
        assert ssh("sha256sum /data/dhparam.pem") == before
    finally:
        ssh("mv /data/dhparam.pem.bak /data/dhparam.pem")


def test_setup_self_signed_cert_for_ui():
    original_ui_cert_id = call("system.general.config")["ui_certificate"]
    created = []
    try:
        # No certificate by that name yet: a self-signed one is generated and
        # installed as the UI certificate.
        call("certificate.setup_self_signed_cert_for_ui", "self_signed_ui")
        cert = call("certificate.query", [["name", "=", "self_signed_ui"]], {"get": True})
        created.append(cert["id"])
        assert call("system.general.config")["ui_certificate"] == cert["id"]

        # Called again with the same name the existing certificate is reused.
        call("certificate.setup_self_signed_cert_for_ui", "self_signed_ui")
        assert call("system.general.config")["ui_certificate"] == cert["id"]
    finally:
        call(
            "datastore.update",
            "system.settings",
            call("system.general.config")["id"],
            {"stg_guicertificate": original_ui_cert_id},
        )
        call("service.control", "START", "ssl", job=True)
        for cert_id in created:
            call("certificate.delete", cert_id, job=True)


def test_setup_self_signed_cert_for_ui_name_taken_by_unusable_certificate():
    # A CSR cannot be used by the UI, so the name gets a numeric suffix and a
    # brand new self-signed certificate is generated under it.
    original_ui_cert_id = call("system.general.config")["ui_certificate"]
    with certificate_signing_request("self_signed_taken") as csr:
        try:
            call("certificate.setup_self_signed_cert_for_ui", csr["name"])
            cert = call("certificate.query", [["name", "=", f"{csr['name']}_1"]], {"get": True})
            assert cert["cert_type_existing"] is True, cert
            assert call("system.general.config")["ui_certificate"] == cert["id"]
        finally:
            call(
                "datastore.update",
                "system.settings",
                call("system.general.config")["id"],
                {"stg_guicertificate": original_ui_cert_id},
            )
            call("service.control", "START", "ssl", job=True)
            for leftover in call("certificate.query", [["name", "=", f"{csr['name']}_1"]]):
                call("certificate.delete", leftover["id"], job=True)
