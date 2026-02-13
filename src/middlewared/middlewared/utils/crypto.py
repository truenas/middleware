from base64 import b64encode
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from ssl import RAND_bytes
from string import ascii_letters, digits, punctuation
from uuid import UUID

from cryptit import cryptit
from middlewared.utils.secrets import choice, token_urlsafe, token_hex

from samba.crypto import md4_hash_blob
from truenas_pyscram import CryptoDatum, generate_scram_auth_data


# NOTE: these are lifted from cpython/Lib/uuid.py
_RFC_4122_CLEARFLAGS_MASK = ~((0xf000 << 64) | (0xc000 << 48))
_RFC_4122_VERSION_4_FLAGS = ((4 << 76) | (0x8000 << 48))


def ssl_random(size: int) -> bytes:
    """ Return the specified number of random bytes from the openssl CSPRNG """
    return RAND_bytes(size)


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


def generate_api_key_auth_data(
    passwd: str,
    salt_in: bytes | None = None,
    rounds: int = 500000
) -> dict[str, str | int]:
    """
    Generate SCRAM authentication data for API key using PBKDF2-SHA512.

    This function derives SCRAM authentication components (client_key, stored_key,
    server_key) from a password using PBKDF2-SHA512 key derivation and SCRAM-SHA-512.

    Args:
        passwd: The password/API key to derive authentication data from.
        salt_in: Optional 16-byte salt. If not provided, a random salt is generated.
        rounds: Number of PBKDF2 iterations (default: 500000).

    Returns:
        Dictionary containing base64-encoded SCRAM authentication components:
            - iterations: Number of PBKDF2 rounds used
            - salt: Base64-encoded salt (16 bytes)
            - client_key: Base64-encoded SCRAM ClientKey
            - stored_key: Base64-encoded SCRAM StoredKey
            - server_key: Base64-encoded SCRAM ServerKey

    Raises:
        ValueError: If salt_in is provided but not exactly 16 bytes.
        TypeError: If rounds is not an integer.

    Note:
        To regenerate the same SCRAM keys for an existing API key, the original
        salt must be provided via salt_in parameter.
    """
    salt_length = 16
    if salt_in:
        if len(salt_in) != salt_length:
            raise ValueError(f'{len(salt_in)}: unexpected salt length')

        salt = CryptoDatum(salt_in)
    else:
        salt = CryptoDatum(generate_string(string_size=salt_length, extra_chars='./').encode())

    if not isinstance(rounds, int):
        raise TypeError(f'Expected int for rounds, got {type(rounds)}')

    thehash = CryptoDatum(pbkdf2_hmac('sha512', passwd.encode(), salt, rounds))
    scram_auth = generate_scram_auth_data(salted_password=thehash, salt=salt, iterations=rounds)

    return {
        'iterations': rounds,
        'salt': b64encode(bytes(scram_auth.salt)).decode(),
        'client_key': b64encode(bytes(scram_auth.client_key)).decode(),
        'stored_key': b64encode(bytes(scram_auth.stored_key)).decode(),
        'server_key': b64encode(bytes(scram_auth.server_key)).decode(),
    }


def ssl_uuid4():
    """
    Generate a random UUID using SSL RAND_bytes. Based on uuid4 from cpython with os.urandom replaced.
    """
    int_uuid_4 = int.from_bytes(RAND_bytes(16))
    int_uuid_4 &= _RFC_4122_CLEARFLAGS_MASK
    int_uuid_4 |= _RFC_4122_VERSION_4_FLAGS
    return UUID(int=int_uuid_4)
