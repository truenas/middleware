from __future__ import annotations

from typing import Any, TYPE_CHECKING

from middlewared.api.base.handler.accept import validate_model
from middlewared.service_exception import ValidationErrors


if TYPE_CHECKING:
    from truenas_pylibvirt.device.base import Device
    from .delegate import DeviceDelegate


class DeviceAdapter:

    def __init__(self, device: Device, data: dict[str, Any]):
        self.pylibvirt_device: Device = device
        self.delegate: DeviceDelegate = device.device_delegate
        self.data = data

    def validate(
        self, old: dict | None = None, instance: dict | None = None, update: bool = True
    ) -> None:
        verrors = ValidationErrors()

        dump = validate_model(self.delegate.schema_model, self.data['attributes'])
        self.data['attributes'] = dump

        device_errors = self.pylibvirt_device.validate()
        for field, error in device_errors:
            verrors.add(f'attributes.{field}', error)

        self.delegate.validate_middleware(self.data, verrors, old, instance, update)

        verrors.check()
