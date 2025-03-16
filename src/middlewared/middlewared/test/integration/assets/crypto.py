import contextlib

from middlewared.test.integration.utils import call


def get_cert_params():
    return {
        'key_type': 'RSA',
        'key_length': 4096,
        'san': ['domain1', '8.8.8.8'],
        'common': 'dev',
        'country': 'US',
        'state': 'TN',
        'city': 'Knoxville',
        'organization': 'iX',
        'organizational_unit': 'dev',
        'email': 'dev@ix.com',
        'digest_algorithm': 'SHA256',
        'cert_extensions': {},
    }


@contextlib.contextmanager
def certificate_signing_request(csr_name):
    cert_params = get_cert_params()
    csr = call('certificate.create', {
        'name': csr_name,
        'create_type': 'CERTIFICATE_CREATE_CSR',
        **cert_params,
    }, job=True)

    try:
        yield csr
    finally:
        call('certificate.delete', csr['id'], job=True)
