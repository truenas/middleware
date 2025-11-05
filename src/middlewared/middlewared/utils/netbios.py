import re

# NetBIOS domain names allow using a dot "." to define a NetBIOS scope
# This is not true for NetBIOS computer names
RE_NETBIOSNAME = re.compile(r"^(?![0-9]*$)[a-zA-Z0-9-_!@#\$%^&\(\)'\{\}~]{1,15}$")
RE_NETBIOSDOM = re.compile(r"^(?![0-9]*$)[a-zA-Z0-9\.\-_!@#\$%^&\(\)'\{\}~]{1,15}$")
NETBIOSNAME_MAX_LEN = 15

MS_RESERVED_WORDS = frozenset([
    'ANONYMOUS'.casefold(),
    'AUTHENTICATED USER'.casefold(),
    'BATCH'.casefold(),
    'BUILTIN'.casefold(),
    'DIALUP'.casefold(),
    # Although DOMAIN is a reserved keyword per microsoft documentation, we have a customer
    # who decided to name their AD domain "DOMAIN". Hence, this part of validation is removed
    # but left commented-out to avoid someone re-introducing the validation in the future.
    # 'DOMAIN'.casefold(),
    'ENTERPRISE'.casefold(),
    'INTERACTIVE'.casefold(),
    'INTERNET'.casefold(),
    # DITTO for LOCAL
    # 'LOCAL'.casefold(),
    'NETWORK'.casefold(),
    'NULL'.casefold(),
    'PROXY'.casefold(),
    'RESTRICTED'.casefold(),
    'SELF'.casefold(),
    # DITTO for server
    # 'SERVER'.casefold(),
    'USERS'.casefold(),
    'WORLD'.casefold()
])

RFC_852_RESERVED_WORDS = frozenset([
    'GATEWAY'.casefold(),
    'GW'.casefold(),
    'TAC'.casefold(),
])

RESERVED_WORDS = frozenset(MS_RESERVED_WORDS | RFC_852_RESERVED_WORDS)


def __validate_netbios_name(val: str, regex: re.Pattern) -> str:
    if not regex.match(val):
        raise ValueError(
            'Invalid NetBIOS name. NetBIOS names must be between 1 and 15 characters in '
            'length and may not contain the following characters: \\/:*?"<>|.'
        )

    if val.casefold() in RESERVED_WORDS:
        raise ValueError(
            f'NetBIOS names may not be one of following reserved names: {", ".join(RESERVED_WORDS)}'
        )

    if len(val) > NETBIOSNAME_MAX_LEN:
        raise ValueError(
            'NetBIOS names may not exceed 15 characters.'
        )

    return val


def validate_netbios_domain(val: str) -> str:
    return __validate_netbios_name(val, RE_NETBIOSDOM)


def validate_netbios_name(val: str) -> str:
    return __validate_netbios_name(val, RE_NETBIOSNAME)
