import re

from cryptography import x509

from truenas_crypto_utils.key import export_private_key


# Cert locations
CERT_ROOT_PATH = '/etc/certificates'
DEFAULT_CERT_NAME = 'truenas_default'
EC_CURVES = [
    'SECP256R1',
    'SECP384R1',
    'SECP521R1',
    'ed25519',
]  # FIXME: See if we can remvoe thisn ow
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


def get_private_key(data: dict) -> str:
    private_key = data['private_key']
    if 'passphrase' in data:
        private_key = export_private_key(data['privatekey'], data['passphrase'])

    return private_key


def _set_required(name):
    def set_r(attr):
        attr.required = True
    return {'name': name, 'method': set_r}
