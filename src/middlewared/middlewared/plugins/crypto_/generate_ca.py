import typing

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from .extensions_utils import add_extensions
from .generate_utils import generate_builder, normalize_san
from .key_utils import export_private_key_object, generate_private_key, retrieve_signing_algorithm
from .load_utils import load_certificate, load_private_key
from .utils import CERT_BACKEND_MAPPINGS, EC_CURVE_DEFAULT


def generate_certificate_authority(data: dict) -> typing.Tuple[str, str]:
    key = generate_private_key({
        'type': data.get('key_type') or 'RSA',
        'curve': data.get('ec_curve') or EC_CURVE_DEFAULT,
        'key_length': data.get('key_length') or 2048
    })

    if data.get('ca_privatekey'):
        ca_key = load_private_key(data['ca_privatekey'])
    else:
        ca_key = None

    san_list = normalize_san(data.get('san') or [])

    builder_data = {
        'crypto_subject_name': {
            k: data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
        },
        'san': san_list,
        'serial': data.get('serial'),
        'lifetime': data.get('lifetime')
    }
    if data.get('ca_certificate'):
        ca_data = load_certificate(data['ca_certificate'])
        builder_data['crypto_issuer_name'] = {
            k: ca_data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
        }
        issuer = x509.load_pem_x509_certificate(data['ca_certificate'].encode(), default_backend())
    else:
        issuer = None

    cert = add_extensions(generate_builder(builder_data), data.get('cert_extensions'), key, issuer)

    cert = cert.sign(
        ca_key or key, retrieve_signing_algorithm(data, ca_key or key), default_backend()
    )

    return cert.public_bytes(serialization.Encoding.PEM).decode(), export_private_key_object(key)
