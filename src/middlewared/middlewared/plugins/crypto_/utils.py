import re

from cryptography import x509


# This constant defines the default lifetime of certificate ( https://support.apple.com/en-us/HT211025 )
DEFAULT_LIFETIME_DAYS = 397
EC_CURVES = [
    'BrainpoolP512R1',
    'BrainpoolP384R1',
    'BrainpoolP256R1',
    'SECP256K1',
    'ed25519',
]
EC_CURVE_DEFAULT = 'BrainpoolP384R1'
EKU_OIDS = [i for i in dir(x509.oid.ExtendedKeyUsageOID) if not i.startswith('__')]
RE_CERTIFICATE = re.compile(r"(-{5}BEGIN[\s\w]+-{5}[^-]+-{5}END[\s\w]+-{5})+", re.M | re.S)
