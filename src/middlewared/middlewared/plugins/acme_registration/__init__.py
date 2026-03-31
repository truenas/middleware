from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.service import GenericCRUDService

from .crud import ACMERegistrationServicePart
from .models import (
    ACMERegistrationCreate,
    ACMERegistrationCreateArgs,
    ACMERegistrationCreateResult,
    ACMERegistrationEntry,
)

if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('ACMERegistrationService',)


class ACMERegistrationService(GenericCRUDService[ACMERegistrationEntry]):

    class Config:
        namespace = 'acme.registration'
        cli_namespace = 'system.acme.registration'
        entry = ACMERegistrationEntry
        role_prefix = 'NETWORK_INTERFACE'
        private = True
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = ACMERegistrationServicePart(self.context)

    @api_method(ACMERegistrationCreateArgs, ACMERegistrationCreateResult, check_annotations=True)
    def do_create(self, data: ACMERegistrationCreate) -> ACMERegistrationEntry:
        """Register with ACME Server"""
        return self._svc_part.do_create(data)
