import typing

from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, ed448, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from middlewared.schema import accepts, Bool, Dict, Int, Str

from .load_utils import load_private_key
from .utils import EC_CURVES


@accepts(
    Dict(
        'generate_private_key',
        Bool('serialize', default=False),
        Int('key_length', default=2048),
        Str('type', default='RSA', enum=['RSA', 'EC']),
        Str('curve', enum=EC_CURVES, default='BrainpoolP384R1')
    )
)
def generate_private_key(options: dict) -> typing.Union[
    str,
    ed25519.Ed25519PrivateKey,
    ed448.Ed448PrivateKey,
    rsa.RSAPrivateKey,
    dsa.DSAPrivateKey,
    ec.EllipticCurvePrivateKey,
]:
    # We should make sure to return in PEM format
    # Reason for using PKCS8
    # https://stackoverflow.com/questions/48958304/pkcs1-and-pkcs8-format-for-rsa-private-key

    if options.get('type') == 'EC':
        if options['curve'] == 'ed25519':
            key = Ed25519PrivateKey.generate()
        else:
            key = ec.generate_private_key(
                getattr(ec, options.get('curve')),
                default_backend()
            )
    else:
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=options.get('key_length'),
            backend=default_backend()
        )

    if options.get('serialize'):
        return key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
    else:
        return key


def export_private_key(buffer: str, passphrase: typing.Optional[str] = None) -> typing.Optional[str]:
    key = load_private_key(buffer, passphrase)
    if key:
        return export_private_key_object(key)


def export_private_key_object(key: typing.Union[
    ed25519.Ed25519PrivateKey,
    ed448.Ed448PrivateKey,
    rsa.RSAPrivateKey,
    dsa.DSAPrivateKey,
    ec.EllipticCurvePrivateKey,
]) -> typing.Optional[str]:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()

