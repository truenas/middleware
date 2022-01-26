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
        'lifetime': 397,
        'serial': 12931,
        'cert_extensions': {},
    }


@contextlib.contextmanager
def root_certificate_authority(name):
    ca = call('certificateauthority.create', {
        **get_cert_params(),
        'name': name,
        'create_type': 'CA_CREATE_INTERNAL',
    })

    try:
        yield ca
    finally:
        call('certificateauthority.delete', ca['id'])


@contextlib.contextmanager
def intermediate_certificate_authority(root_ca_name, intermediate_ca_name):
    with root_certificate_authority(root_ca_name) as root_ca:
        intermediate_ca = call('certificateauthority.create', {
            **get_cert_params(),
            'signedby': root_ca['id'],
            'name': intermediate_ca_name,
            'create_type': 'CA_CREATE_INTERNAL',
        })

        try:
            yield root_ca, intermediate_ca
        finally:
            call('certificateauthority.delete', intermediate_ca['id'])
