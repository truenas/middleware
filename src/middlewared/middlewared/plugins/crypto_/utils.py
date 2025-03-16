import re

from cryptography import x509


CERT_BACKEND_MAPPINGS = {
    'common_name': 'common',
    'country_name': 'country',
    'state_or_province_name': 'state',
    'locality_name': 'city',
    'organization_name': 'organization',
    'organizational_unit_name': 'organizational_unit',
    'email_address': 'email'
}
RDN_MAPPINGS = {
    'C': 'country_name',
    'country': 'country_name',
    'ST': 'state_or_province_name',
    'state': 'state_or_province_name',
    'L': 'locality_name',
    'city': 'locality_name',
    'O': 'organization_name',
    'organization': 'organization_name',
    'OU': 'organizational_unit_name',
    'organizational_unit': 'organizational_unit_name',
    'CN': 'common_name',
    'common': 'common_name',
    'emailAddress': 'email_address',
    'email': 'email_address'
}
# Cert locations
CERT_ROOT_PATH = '/etc/certificates'
CERT_CA_ROOT_PATH = '/etc/certificates/CA'
DEFAULT_CERT_NAME = 'truenas_default'
# This constant defines the default lifetime of certificate ( https://support.apple.com/en-us/HT211025 )
DEFAULT_LIFETIME_DAYS = 397
EC_CURVES = [
    'SECP256R1',
    'SECP384R1',
    'SECP521R1',
    'ed25519',
]
EC_CURVE_DEFAULT = 'SECP384R1'
EKU_OIDS = [i for i in dir(x509.oid.ExtendedKeyUsageOID) if not i.startswith('__')]
RE_CERTIFICATE = re.compile(r"(-{5}BEGIN[\s\w]+-{5}[^-]+-{5}END[\s\w]+-{5})+", re.M | re.S)

# Defining cert constants being used
CERT_TYPE_EXISTING = 0x08
CERT_TYPE_CSR = 0x20


def get_cert_info_from_data(data):
    cert_info_keys = [
        'key_length', 'country', 'state', 'city', 'organization', 'common', 'key_type', 'ec_curve',
        'san', 'serial', 'email', 'lifetime', 'digest_algorithm', 'organizational_unit'
    ]
    return {key: data.get(key) for key in cert_info_keys if data.get(key)}


def _set_required(name):
    def set_r(attr):
        attr.required = True
    return {'name': name, 'method': set_r}
