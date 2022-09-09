import secrets
from string import ascii_letters, digits, punctuation


def generate_string(string_size=8, punctuation_chars=False):
    """
    Generate a cryptographically secure random string of size `string_size`.
    If `punctuation_chars` is True, then punctuation characters will be added to the string.
    Otherwise, only ASCII (upper and lower) and digits (0-9) are used to generate the string.
    """
    initial_string = ascii_letters + digits
    if punctuation_chars:
        initial_string += punctuation

    return ''.join(secrets.choice(initial_string) for i in range(string_size))


def generate_token(size, url_safe=False):
    """
    Generate a cryptographically secure token of `size` in bytes returned in hex format.

    `url_safe` when True, returns the token using url safe characters only.
    """
    if url_safe:
        return secrets.token_urlsafe(size)
    else:
        return secrets.token_hex(size)
