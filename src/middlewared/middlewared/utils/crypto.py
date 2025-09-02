from base64 import b64encode
from dataclasses import dataclass
from enum import StrEnum
from hashlib import pbkdf2_hmac
from secrets import choice, compare_digest, token_urlsafe, token_hex
from ssl import RAND_bytes
from string import ascii_letters, digits, punctuation
from uuid import UUID

from cryptit import cryptit

from samba.crypto import md4_hash_blob

from truenas_api_client import scram_impl


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


def generate_scram_data(passwd: str, rounds: int = 500000, salt: bytes | None = None) -> dict:
    """
    Generate SCRAM server data and client key based on provided password and salt / rounds.
    If salt is None then new salt will be generated.
    """
    if salt is None:
        salt = generate_string(string_size=16, extra_chars='./').encode()

    thehash = pbkdf2_hmac('sha512', passwd.encode(), salt, rounds)
    server_key = scram_impl.create_scram_server_key(thehash)
    client_key = scram_impl.create_scram_client_key(thehash)
    stored_key = scram_impl.h(client_key)) 

    return TNScramData(
        algorithm='sha-512',
        salt=salt,
        iteration_count=rounds,
        stored_key=stored_key,
        server_key=server_key,
        client_key=client_key
    )


def legacy_api_key_hash_string_to_scram_server_data(hash_str: str) -> TNScramServerData:
    """
    Convert an existing API key hash (created thorugh generate_pkgdf2_512()) to server SCRAM
    data. This method exists primarily for migration of existing API keys to the new format.
    """
    prefix, rounds, salt, thehash = hash_str.split('$')[1:]
    salted_key = b64decode(thehash)
    server_key = scram_impl.create_scram_server_key(thehash)
    stored_key = scram_impl.h(scram_impl.create_scram_client_key(thehash)) 

    return TNScramData(
        algorithm='sha-512',
        salt=b64decode(salt),
        iteration_count=int(rounds),
        stored_key=stored_key,
        server_key=server_key
    )


def validate_plain_api_key_scram(passwd: str, server_data: TNScramServerData) -> bool:
    """
    Check whether the provided plain-text password / api key matches the one that generated
    our local SCRAM server data. This is used to implement plain password validation for
    compatibliity with the API_KEY_PLAIN authentication mechanism. 
    """
    scram_data = generate_scram_data(passwd, server_data.iteration_count, server_data.salt)
    return hmac.compare_digest(scram_data.server_key, server_data.server_key)
