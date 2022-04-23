from secrets import choice, randbits, SystemRandom
from string import ascii_letters, digits, punctuation

SR = SystemRandom()


def random_string(string_size=8, punctuation_chars=False):
    """
    Generate a cryptographically secure random string of size `string_size`.

    If `punctuation_chars` is True, then punctuation
    characters will be added to the string.

    Otherwise, only ASCII (upper and lower) and
    digits (0-9) are used to generate the string.
    """
    initial_string = ascii_letters + digits
    if punctuation_chars:
        initial_string += punctuation

    return ''.join(choice(initial_string) for i in range(string_size))


def random_bits(size):
    """
    Generate an integer with `size` random bits.
    """
    return randbits(size)


def random_int(start, end):
    """
    Generate a random integer in range [`start`, `end`] inclusive.
    """
    return SR.randint(start, end)


def random_uniform(a, b):
    """
    Get a random number (float) in range [`a`, `b`), or [`a`, `b`] depending on rounding.
    """
    return SR.uniform(a, b)
