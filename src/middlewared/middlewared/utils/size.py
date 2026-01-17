import humanfriendly
import re
import types


DECIMAL_UNITS = types.MappingProxyType(
    {
        '': 1,
        'B': 1,
        'K': 10**3,
        'KB': 10**3,
        'M': 10**6,
        'MB': 10**6,
        'G': 10**9,
        'GB': 10**9,
        'T': 10**12,
        'TB': 10**12,
        'P': 10**15,
        'PB': 10**15,
        'E': 10**18,
        'EB': 10**18,
        'Z': 10**21,
        'ZB': 10**21,
    }
)
BINARY_UNITS = types.MappingProxyType(
    {
        'KI': 2**10,
        'KIB': 2**10,
        'MI': 2**20,
        'MIB': 2**20,
        'GI': 2**30,
        'GIB': 2**30,
        'TI': 2**40,
        'TIB': 2**40,
        'PI': 2**50,
        'PIB': 2**50,
        'EI': 2**60,
        'EIB': 2**60,
        'ZI': 2**70,
        'ZIB': 2**70,
    }
)
MB = 1048576
RE_SIZE = re.compile(r'([\d\.]+)\s*([A-Za-z]*)')


def format_size(size: int) -> str:
    return humanfriendly.format_size(size, binary=True)


def normalize_size(size: str, raise_exception: bool = True) -> int | None:
    """
    Convert a size string (e.g., '1GB', '1GiB', '1G', '10M', '24B') into bytes.
    Supports both decimal (GB, MB, etc.) and binary (GiB, MiB, etc.) prefixes.

    Args:
        raise_exception: bool, when True will raise a ValueError in the event
        the `size` argument doesn't match a valid unit.

        size: str, the size string to convert into bytes.
    """
    if not isinstance(size, str):
        return size

    size = size.strip().upper()
    match = RE_SIZE.match(size)
    if not match:
        if raise_exception:
            raise ValueError(f'Invalid size format: {size}')
        return None

    value, unit = match.groups()
    value = float(value)
    unit = unit.upper()
    try:
        return int(value * DECIMAL_UNITS[unit])
    except KeyError:
        pass

    try:
        return int(value * BINARY_UNITS[unit])
    except KeyError:
        pass

    if raise_exception:
        raise ValueError(f'Invalid size format: {size}')
    return None
