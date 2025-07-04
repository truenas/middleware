import textwrap

import pytest

from middlewared.plugins.apps.schema_normalization import AppSchemaService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('cert, value, should_work', [
    (
        textwrap.dedent(
            '''
            -----BEGIN CERTIFICATE-----
            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
            -----END CERTIFICATE-----
            '''
        ),
        12,
        True
    ),
    (
        textwrap.dedent(
            '''
            -----BEGIN CERTIFICATE-----
            MIIFmzCCA4OgAwIBAgICMoMwDQYJKoZIhvcNAQELBQAwcjEMMAoGA1UEAwwDZGV2
            MQswCQYDVQQGEwJVUzELMAkGA1UECAwCVE4xEjAQBgNVBAcMCUtub3h2aWxsZTEL
            MAkGA1UECgwCaVgxDDAKBgNVBAsMA2RldjEZMBcGCSqGSIb3DQEJARYKZGV2QGl4
            LmNvbTAeFw0yMjAxMjQxOTI0MTRaFw0yMzAyMjUxOTI0MTRaMHIxDDAKBgNVBAMM
            A2RldjELMAkGA1UEBhMCVVMxCzAJBgNVBAgMAlROMRIwEAYDVQQHDAlLbm94dmls
            bGUxCzAJBgNVBAoMAmlYMQwwCgYDVQQLDANkZXYxGTAXBgkqhkiG9w0BCQEWCmRl
            dkBpeC5jb20wggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQDuy5kKf7eT
            LOuxm1pn51kFLgJHD6k05pROjMOXEZel7CsmrDKEehSSdwDB/WUim3idOsImLrc+
            ApXsnKwVY93f7yn1rfF4lgKsa3sb6oqAcPEobgTUqSmJ/OQVilUqOtj/dmFaEWIS
            21eKNzaByNdpyOcoRF/+uDylEsE1Gj0GjkBneVRxyTZFV7LdVyDk38hljesnd8FX
            gnD0DCdI3jBvqSYvd+GvQ2nQ2624HAmEQwfllqKi9PRDngeZIeiTQSWN+rybJbDY
            yonRS0FPxJydt/sDlzi43qzHnrTqUbL+2RjYIqcOqeivNtDZ2joh+xqfRdKzACWu
            QWrhGCL5+9bnqA6PEPA7GQ2jp00gDkjB7+HlQLI8ZCZcST6mkbfs/EaW00WYIcw5
            lb+5oJ8oJqWebnQB21iwvPjvAv353iA1ApTJxBdo13x7oXBwWsrpxWk6SdL2Z5zU
            NXrC9ZyaoeQ5uZ/oBXbCxJfhSkISyI5D8yeYLjmMxn+AvRBQpkRmVvcy3ls2SHGX
            4XEJ4Q0wj3a0rPqmDZUwpWErbmf+N6D7J+uK8n3pcGlvkFIUaP60UQGp4gwnZA2O
            dZdhVQ4whQHyjTmL7kRKl+gR/vTp+iPvKMfTO1HBQp97iK8IPM7Q2Gpe6U4n/Ll2
            TDaZ9DroM83Vnc6cX69Th555SA9+gP6HWQIDAQABozswOTAYBgNVHREEETAPggdk
            b21haW4xhwQICAgIMB0GA1UdDgQWBBSz0br/9U9mwYZfuRO1JmKTEorq1DANBgkq
            hkiG9w0BAQsFAAOCAgEAK7nBNA+qjgvkmcSLQC+yXPOwb3o55D+N0J2QLxJFT4NV
            b0GKf0dkz92Ew1pkKYzsH6lLlKRE23cye6EZLIwkkhhF0sTwYeu8HNy7VmkSDsp0
            aKbqxgBzIJx+ztQGNgZ1fQMRjHCRLf8TaSAxnVXaXXUeU6fUBq2gHbYq6BfZkGmU
            6f8DzL7uKHzcMEmWfC5KxfSskFFPOyaz/VGViQ0yffwH1NB+txDlU58rmu9w0wLe
            cOrOjVUNg8axQen2Uejjj3IRmDC18ZfY7EqI8O1PizCtIcPSm+NnZYg/FvVj0KmM
            o2QwGMd5QTU2J5lz988Xlofm/r3GBH32+ETqIcJolBw9bBkwruBvHpcmyLSFcFWK
            sdGgi2gK2rGb+oKwzpHSeCtQVwgQth55qRH1DQGaAdpA1uTriOdcR96i65/jcz96
            aD2B958hF1B/7I4Md+LFYhxgwREBhyQkU6saf7GR0Q+p4F8/oIkjhdLsyzk4YHyI
            PVtK00W8zQMKF6zhHjfaF2uDRO/ycMKCq9NIqQJCZNqwNAo0r4FOmilwud/tzFY8
            GQ9FXeQSqWo7hUIXdbej+aJ7DusYeuE/CwQFNUnz1khvIFJ5B7YP+gYCyUW7V2Hr
            Mv+cZ473U8hYQ1Ij7pXi7DxsOWqWCDhyK0Yp6MZsw0rNaAIPHnTTxYdMfmIYHT0=
            -----END CERTIFICATE-----
            '''
        ),
        None,
        False
    ),

], ids=['valid_cert', 'invalid_cert'])
@pytest.mark.asyncio
async def test_normalize_certificate(cert, value, should_work):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    middleware['certificate.get_instance'] = lambda *args: cert
    complete_config = {'ix_certificates': {value: cert}}
    result = await app_schema_obj.normalize_certificate({'schema': {'type': 'int'}}, value, complete_config, '')
    if should_work:
        assert result is not None
    else:
        assert result is None
