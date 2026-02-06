# Python secrets module equalivalent based on openssl RAND_bytes rather than os.urandom

from base64 import urlsafe_b64encode
from random import Random, RECIP_BPF  # type: ignore[attr-defined]
from secrets import DEFAULT_ENTROPY  # type: ignore[attr-defined]
from ssl import RAND_bytes
from typing import Any


class SSLRandom(Random):
    """
    Alternate random number generator using ssl RAND_bytes.
    Based on SystemRandom class in cpython/Lib/random.py
    """

    def random(self) -> float:
        """Get the next random number in the range 0.0 <= X < 1.0."""
        return (int.from_bytes(RAND_bytes(7)) >> 3) * RECIP_BPF  # type: ignore[no-any-return]

    def getrandbits(self, k: int) -> int:
        """getrandbits(k) -> x.  Generates an int with k random bits."""
        if k < 0:
            raise ValueError('number of bits must be non-negative')
        numbytes = (k + 7) // 8                       # bits / 8 and rounded up
        x = int.from_bytes(RAND_bytes(numbytes))
        return x >> (numbytes * 8 - k)                # trim excess bits

    def randbytes(self, n: int) -> bytes:
        """Generate n random bytes."""
        # os.urandom(n) fails with ValueError for n < 0
        # and returns an empty bytes string for n == 0.
        return RAND_bytes(n)

    def seed(self, *args: Any, **kwds: Any) -> None:
        """Stub method.  Not used for a system random number generator."""
        return None

    def _notimplemented(self, *args: Any, **kwds: Any) -> None:
        """Method should not be called for a system random number generator."""
        raise NotImplementedError('System entropy source does not have state.')
    getstate = setstate = _notimplemented  # type: ignore[assignment]


_sslrand = SSLRandom()
choice = _sslrand.choice
randbits = _sslrand.getrandbits


def token_bytes(nbytes: int | None = None) -> bytes:
    """Return a random byte string containing *nbytes* bytes.

    If *nbytes* is ``None`` or not supplied, a reasonable
    default is used.

    >>> token_bytes(16)
    b'\\xebr\\x17D*t\\xae\\xd4\\xe3S\\xb6\\xe2\\xebP1\\x8b'

    """
    if nbytes is None:
        nbytes = DEFAULT_ENTROPY
    return _sslrand.randbytes(nbytes)


def token_hex(nbytes: int | None = None) -> str:
    """Return a random text string, in hexadecimal.

    The string has *nbytes* random bytes, each byte converted to two
    hex digits.  If *nbytes* is ``None`` or not supplied, a reasonable
    default is used.

    >>> token_hex(16)
    'f9bf78b9a18ce6d46a0cd2b0b86df9da'

    """
    return token_bytes(nbytes).hex()


def token_urlsafe(nbytes: int | None = None) -> str:
    """Return a random URL-safe text string, in Base64 encoding.

    The string has *nbytes* random bytes.  If *nbytes* is ``None``
    or not supplied, a reasonable default is used.

    >>> token_urlsafe(16)
    'Drmhze6EPcv0fN_81Bj-nA'

    """
    tok = token_bytes(nbytes)
    return urlsafe_b64encode(tok).rstrip(b'=').decode('ascii')
