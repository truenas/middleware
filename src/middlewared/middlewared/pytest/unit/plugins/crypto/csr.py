import pytest

from cryptography.hazmat.primitives.asymmetric import rsa

from middlewared.plugins.crypto_.csr import generate_certificate_signing_request
from middlewared.plugins.crypto_.load_utils import load_certificate_request, load_private_key


@pytest.mark.parametrize('generate_params,key_type,key_size,csr_info', [
    (
        {
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
        },
        rsa.RSAPrivateKey, 4096,
        {
            'DN': '/CN=dev/C=US/ST=TN/L=Knoxville/O=iX/OU=dev/emailAddress=dev@ix.com/subjectAltName='
                  'DNS:domain1, IP Address:8.8.8.8',
            'city': 'Knoxville',
            'common': 'dev',
            'country': 'US',
            'email': 'dev@ix.com',
            'extensions': {'SubjectAltName': 'DNS:domain1, IP Address:8.8.8.8'},
            'organization': 'iX',
            'organizational_unit': 'dev',
            'san': ['DNS:domain1', 'IP Address:8.8.8.8'],
            'state': 'TN',
            'subject_name_hash': None,
        }
    ),
    (
        {
            'key_type': 'RSA',
            'key_length': 2048,
            'san': ['domain2', '9.9.9.9'],
            'common': 'dev2',
            'country': 'US',
            'state': 'TN',
            'city': 'Newyork',
            'organization': 'iX-devs',
            'organizational_unit': 'dev-dept',
            'email': 'info@ix.com',
            'digest_algorithm': 'SHA256',
        },
        rsa.RSAPrivateKey, 2048,
        {
            'DN': '/CN=dev2/C=US/ST=TN/L=Newyork/O=iX-devs/OU=dev-dept/emailAddress=info@ix.com/'
                  'subjectAltName=DNS:domain2, IP Address:9.9.9.9',
            'city': 'Newyork',
            'common': 'dev2',
            'country': 'US',
            'email': 'info@ix.com',
            'extensions': {'SubjectAltName': 'DNS:domain2, IP Address:9.9.9.9'},
            'organization': 'iX-devs',
            'organizational_unit': 'dev-dept',
            'san': ['DNS:domain2', 'IP Address:9.9.9.9'],
            'state': 'TN',
            'subject_name_hash': None
        }
    ),
])
def test_generating_private_key(generate_params, key_type, key_size, csr_info):
    csr, key = generate_certificate_signing_request(generate_params)
    csr_details = load_certificate_request(csr)
    key_obj = load_private_key(key)
    assert csr_details == csr_info, csr_details
    assert isinstance(key_obj, rsa.RSAPrivateKey) is True
    assert key_type.key_size == key_size
