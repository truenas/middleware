from __future__ import annotations

import typing

from middlewared.api.current import AppEntry
from middlewared.service import CRUDServicePart


if typing.TYPE_CHECKING:
    from middlewared.job import Job


class AppServicePart(CRUDServicePart[AppEntry]):
    _entry: AppEntry
