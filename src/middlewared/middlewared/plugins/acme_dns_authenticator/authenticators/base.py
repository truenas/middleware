from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from middlewared.service import CallError

if TYPE_CHECKING:
    from middlewared.api.base import BaseModel
    from middlewared.main import Middleware


class Authenticator:

    NAME: str
    PROPAGATION_DELAY: float
    SCHEMA_MODEL: type[BaseModel]
    INTERNAL: bool = False

    def __init__(self, middleware: Middleware, attributes: dict[str, Any]) -> None:
        self.middleware = middleware
        self.attributes = attributes
        self.initialize_credentials()

    def initialize_credentials(self) -> None:
        pass

    @staticmethod
    async def validate_credentials(middleware: Middleware, data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def perform(self, domain: str, validation_name: str, validation_content: str) -> None:
        try:
            perform_ret = self._perform(domain, validation_name, validation_content)
        except Exception as e:
            raise CallError(f"Failed to perform {self.NAME} challenge for {domain!r} domain: {e}")
        else:
            self.wait_for_records_to_propagate(perform_ret)

    def _perform(self, domain: str, validation_name: str, validation_content: str) -> Any:
        raise NotImplementedError

    def wait_for_records_to_propagate(self, perform_ret: Any) -> None:
        time.sleep(self.PROPAGATION_DELAY)

    def cleanup(self, domain: str, validation_name: str, validation_content: str) -> None:
        try:
            self._cleanup(domain, validation_name, validation_content)
        except Exception as e:
            raise CallError(f"Failed to cleanup {self.NAME} challenge for {domain!r} domain: {e}")

    def _cleanup(self, domain: str, validation_name: str, validation_content: str) -> None:
        raise NotImplementedError
