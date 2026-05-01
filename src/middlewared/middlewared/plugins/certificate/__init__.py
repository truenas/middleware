from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    CertificateEntry,
)
from middlewared.service import GenericCRUDService, job, private

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ('CertificateService',)


class CertificateService(GenericCRUDService[CertificateEntry]):

    class Config:
        cli_namespace = 'system.certificate'
        role_prefix = 'CERTIFICATE'
        entry = CertificateEntry
