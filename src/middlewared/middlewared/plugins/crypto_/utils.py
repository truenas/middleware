import re

from cryptography import x509


# Cert locations
CERT_ROOT_PATH = '/etc/certificates'
DEFAULT_CERT_NAME = 'truenas_default'
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
