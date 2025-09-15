import os

try:
    import truenas_pypwenc
except ImportError:
    truenas_pypwenc = None

import threading


PWENC_PADDING = b'{'  # This is for legacy compatibility. aes-256-ctr doesn't need padding
try:
    PWENC_FILE_SECRET = truenas_pypwenc.DEFAULT_SECRET_PATH
except AttributeError:
    # This is just a catchall for some CI that doesn't have truenas_pypwenc installed
    PWENC_FILE_SECRET = '/data/pwenc_secret'

PWENC_FILE_SECRET_MODE = 0o600
pwenc_data = {'secret_ctx': None, 'lock': threading.Lock()}


def pwenc_get_ctx():
    """ Retrieve a truenas_pypwenc() context with secret key
    loaded in memfd secret. This will raise an exception if file
    does not exist. """
    if pwenc_data['secret_ctx']:
        return pwenc_data['secret_ctx']

    with pwenc_data['lock']:
        pwenc_data['secret_ctx'] = truenas_pypwenc.get_context(create=False)

    return pwenc_data['secret_ctx']


def pwenc_encrypt(data_in: bytes) -> bytes:
    """ Encrypt and base64 encode the input bytes """
    ctx = pwenc_get_ctx()
    return ctx.encrypt(data_in)


def pwenc_decrypt(data_in: bytes) -> bytes:
    """ Base64 decode and decrypt the input bytes """
    ctx = pwenc_get_ctx()
    return ctx.decrypt(data_in).rstrip(PWENC_PADDING)


def pwenc_generate_secret():
    """ Create a new pwenc secret. """
    with pwenc_data['lock']:
        try:
            os.unlink(truenas_pypwenc.DEFAULT_SECRET_PATH)
        except FileNotFoundError:
            pass

        pwenc_data['secret_ctx'] = truenas_pypwenc.get_context(create=True)
        assert pwenc_data['secret_ctx'].created


def encrypt(decrypted: str) -> str:
    """ Encrypt the input data string and return a base64 string """
    data = decrypted.encode('utf8')
    encrypted = pwenc_encrypt(data)
    return encrypted.decode()


def decrypt(encrypted: str, _raise=False) -> str:
    """ Decrypt the input base64 string and return a string """
    if not encrypted:
        return ''

    data = encrypted.encode('utf8')

    try:
        decrypted = pwenc_decrypt(data)
        return decrypted.decode('utf8')
    except Exception:
        if _raise:
            raise
        return ''
