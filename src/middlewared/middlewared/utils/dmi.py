"""Process-wide cached view of SMBIOS / DMI for middleware.

:func:`cached_dmi` parses ``/sys/firmware/dmi/tables/*`` on first call and
returns the same :class:`DMIInfo` on every subsequent call. SMBIOS data
is static within a process lifetime, so one parse per worker is enough.
Call ``cached_dmi.cache_clear()`` if you genuinely need to re-read (only
expected in tests).
"""

from functools import cache

from truenas_pydmi.models import DMIInfo
from truenas_pydmi.reader import read_dmi


@cache
def cached_dmi() -> DMIInfo:
    return read_dmi()
