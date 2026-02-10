from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

from truenas_pylibvirt.device.delegate import DeviceDelegate as BaseDeviceDelegate

from middlewared.service_exception import ValidationErrors


if TYPE_CHECKING:
    from middlewared.main import Middleware


class DeviceDelegate(BaseDeviceDelegate, ABC):

    def __init__(self, middleware: Middleware, id_: int | None = None) -> None:
        super().__init__()
        self.middleware: Middleware = middleware
        self.id: int | None = id_

    @property
    @abstractmethod
    def schema_model(self) -> type:
        ...

    def validate_middleware(
        self,
        device: dict[str, Any],
        verrors: ValidationErrors,
        old: dict[str, Any] | None = None,
        instance: dict[str, Any] | None = None,
        update: bool = True,
    ) -> None:
        pass
