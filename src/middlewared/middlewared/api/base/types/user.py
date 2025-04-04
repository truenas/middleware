import string
from typing import Annotated

from pydantic import Field
from pydantic.functional_validators import AfterValidator

from middlewared.utils.sid import sid_is_valid

__all__ = ["LocalUsername", "RemoteUsername", "LocalUID", "LocalGID", "SID", "ContainerXID"]

XID_MAX = 2 ** 32 - 2  # uid_t -1 can have special meaning depending on context
# TRUENAS_IDMAP_MAX + 1
INCUS_IDMAP_MIN = 2147000001
# Each unpriviliged container with isolated idmap will require at least 65536.
# Lets reserve enough so we can run at least 7 of these.
# Increasing this would go above signed 32 bits (>= 2147483648) which might
# cause problems for programs that do not expect it (e.g. filesystems like
# devpts and some syscalls like setfsuid())
INCUS_MAX_ISOLATED_CONTAINER = 7
INCUS_IDMAP_COUNT = 65536 * INCUS_MAX_ISOLATED_CONTAINER
INCUS_IDMAP_MAX = INCUS_IDMAP_MIN + INCUS_IDMAP_COUNT
TRUENAS_IDMAP_DEFAULT_LOW = 90000001

DEFAULT_VALID_CHARS = string.ascii_letters + string.digits + '_' + '-' + '$' + '.'
DEFAULT_VALID_START = string.ascii_letters + '_'
DEFAULT_MAX_LENGTH = 32


def validate_username(
    val: str,
    valid_chars: str = DEFAULT_VALID_CHARS,
    valid_start_chars : str | None = DEFAULT_VALID_START,
    max_length: int | None = DEFAULT_MAX_LENGTH
) -> str:
    val_len = len(val)
    assert val_len > 0, 'Username must be at least 1 character in length'
    if max_length is not None:
        assert val_len <= max_length, f'Username cannot exceed {max_length} charaters in length'
    if valid_start_chars is not None:
        assert val[0] in valid_start_chars, 'Username must start with a letter or an underscore'

    assert '$' not in val or val[-1] == '$', 'Username must end with a dollar sign character'
    assert all(char in valid_chars for char in val), f'Valid characters for a username are: {", ".join(valid_chars)!r}'
    return val


def validate_local_username(val: str) -> str:
    # see man 8 useradd, specifically the CAVEATS section
    # NOTE: we are ignoring the man page's recommendation for insistence
    # upon the starting character of a username be a lower-case letter.
    # We aren't enforcing this for maximum backwards compatibility
    return validate_username(val)


def validate_sid(value: str) -> str:
    value = value.strip()
    value = value.upper()

    assert sid_is_valid(value), ('SID is malformed. See MS-DTYP Section 2.4 for SID type specifications. Typically '
                                 'SIDs refer to existing objects on the local or remote server and so an appropriate '
                                 'value should be queried prior to submitting to API endpoints.')

    return value


LocalUsername = Annotated[str, AfterValidator(validate_local_username)]
RemoteUsername = Annotated[str, Field(min_length=1)]
LocalUID = Annotated[int, Field(ge=0, le=TRUENAS_IDMAP_DEFAULT_LOW - 1)]

LocalGID = Annotated[int, Field(ge=0, le=TRUENAS_IDMAP_DEFAULT_LOW - 1)]

ContainerXID = Annotated[int, Field(ge=1, le=XID_MAX)]

SID = Annotated[str, AfterValidator(validate_sid)]
