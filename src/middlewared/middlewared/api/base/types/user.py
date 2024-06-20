import string

from annotated_types import Ge, Le
from pydantic.functional_validators import AfterValidator
from typing_extensions import Annotated

__all__ = ["LocalUsername", "LocalUID"]

TRUENAS_IDMAP_DEFAULT_LOW = 90000001


def validate_local_username(val):
    # see man 8 useradd, specifically the CAVEATS section
    # NOTE: we are ignoring the man page's recommendation for insistence
    # upon the starting character of a username be a lower-case letter.
    # We aren't enforcing this for maximum backwards compatibility
    val_len = len(val)
    valid_chars = string.ascii_letters + string.digits + '_' + '-' + '$' + '.'
    valid_start = string.ascii_letters + '_'
    assert val_len > 0, 'Username must be at least 1 character in length'
    assert val_len <= 32, 'Username cannot exceed 32 characters in length'
    assert val[0] in valid_start, 'Username must start with a letter or an underscore'
    assert '$' not in val or val[-1] == '$', 'Username must end with a dollar sign character'
    assert all(char in valid_chars for char in val), f'Valid characters for a username are: {", ".join(valid_chars)!r}'
    return val


LocalUsername = Annotated[str, AfterValidator(validate_local_username)]
LocalUID = Annotated[int, Ge(0), Le(TRUENAS_IDMAP_DEFAULT_LOW - 1)]
