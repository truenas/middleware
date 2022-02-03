import pytest
import textwrap

from cryptography.hazmat.primitives.asymmetric import ec, rsa

from middlewared.plugins.crypto_.key_utils import load_private_key, generate_private_key


@pytest.mark.parametrize('generate_params,expected_type,key_size', [
    ({}, rsa.RSAPrivateKey, 2048),
    ({'type': 'EC'}, ec.EllipticCurvePrivateKey, 384),
    (
        {
            'type': 'RSA',
            'key_length': 4096,
        },
        rsa.RSAPrivateKey,
        4096
    ),
])
def test_generating_private_key(generate_params, expected_type, key_size):
    key = generate_private_key(generate_params)
    assert isinstance(key, expected_type) is True
    assert key.key_size == key_size


@pytest.mark.parametrize('key_str,expected_type,key_size', [
    (
        textwrap.dedent('''\
            -----BEGIN PRIVATE KEY-----
            MIG6AgEAMBQGByqGSM49AgEGCSskAwMCCAEBCwSBnjCBmwIBAQQwYTYZ6gXVzx6X
            epQm03qt1oBNJcdy+NN7EslikEJoNDVUWciJRwf39zj/6Z6Ak/vqoWQDYgAEBfty
            8bW+Q7uKykK+5PfGZbimKgcvgNg8JlwJoCWLarO3ApFsq97Ea9jTWfaiCBorSs/R
            fMBj/3QF+zpTv7Djcxmou+PuSs9B2JclOm2ycPbDFRvQ9bNfGjlABNMB42lV
            -----END PRIVATE KEY-----
        '''),
        ec.EllipticCurvePrivateKey, 384
    ),
    (
        textwrap.dedent('''\
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
        '''),
        rsa.RSAPrivateKey, 2048
    ),
])
def test_loading_private_key(key_str, expected_type, key_size):
    key = load_private_key(key_str)
    assert isinstance(key, expected_type) is True
    assert key.key_size == key_size
