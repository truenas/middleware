from base64 import b64encode
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from ssl import RAND_bytes
from string import ascii_letters, digits, punctuation
from uuid import UUID

from cryptit import cryptit
from middlewared.utils.secrets import choice, token_urlsafe, token_hex

from samba.crypto import md4_hash_blob


# NOTE: these are lifted from cpython/Lib/uuid.py
_RFC_4122_CLEARFLAGS_MASK = ~((0xf000 << 64) | (0xc000 << 48))
_RFC_4122_VERSION_4_FLAGS = ((4 << 76) | (0x8000 << 48))


def generate_string(string_size=8, punctuation_chars=False, extra_chars=None):
    """
    Generate a cryptographically secure random string of size `string_size`.
    If `punctuation_chars` is True, then punctuation characters will be added to the string.
    Otherwise, only ASCII (upper and lower) and digits (0-9) are used to generate the string.
    """
    initial_string = ascii_letters + digits
    if punctuation_chars:
        initial_string += punctuation
    if extra_chars is not None and isinstance(extra_chars, str):
        initial_string += extra_chars

    # remove any duplicates since extra_chars is user-provided
    initial_string = ''.join(set(initial_string))
    return ''.join(choice(initial_string) for i in range(string_size))


def generate_token(size, url_safe=False):
    """
    Generate a cryptographically secure token of `size` in bytes returned in hex format.

    `url_safe` when True, returns the token using url safe characters only.
    """
    if url_safe:
        return token_urlsafe(size)
    else:
        return token_hex(size)


def sha512_crypt(word):
    """Generate a hash using the modular crypt format of `word`
    using SHA512 algorithm with rounds set to 656,000 with a
    16-char pseudo-random cryptographically secure salt.
    """
    sha512_prefix = '$6'
    rounds = 656_000
    salt_length = 16
    salt = generate_string(string_size=salt_length, extra_chars='./')
    settings = f'{sha512_prefix}$rounds={rounds}${salt}'
    # note this is thread-safe and releases GIL
    return cryptit(word, settings)


def check_unixhash(passwd, unixhash):
    """Verify that the hash produced by `passwd` matches the
    given `unixhash`.
    """
    return compare_digest(cryptit(passwd, unixhash), unixhash)


def generate_nt_hash(passwd):
    """
    Generate an NT hash for SMB user password. This is required for
    NTLM authentication for local users.

    NOTE: the library generating the NT hash ignores the system
    FIPS mode.

    WARNING: This is a weak algorithm and must be treated as
    plain-text equivalent.
    """
    md4_hash_bytes = md4_hash_blob(passwd.encode('utf-16le'))
    return md4_hash_bytes.hex().upper()


def generate_pbkdf2_512(passwd):
    """
    Generate a pbkdf2_sha512 hash for password. This is used for
    verification of API keys.
    """
    prefix = 'pbkdf2-sha512'
    rounds = 500000
    salt_length = 16
    salt = generate_string(string_size=salt_length, extra_chars='./').encode()
    thehash = pbkdf2_hmac('sha512', passwd.encode(), salt, rounds)
    return f'${prefix}${rounds}${b64encode(salt).decode()}${b64encode(thehash).decode()}'


def ssl_uuid4():
    """
    Generate a random UUID using SSL RAND_bytes. Based on uuid4 from cpython with os.urandom replaced.
    """
    int_uuid_4 = int.from_bytes(RAND_bytes(16))
    int_uuid_4 &= _RFC_4122_CLEARFLAGS_MASK
    int_uuid_4 |= _RFC_4122_VERSION_4_FLAGS
    return UUID(int=int_uuid_4)
