from __future__ import annotations

from typing import Any, TYPE_CHECKING

from truenas_pylibvirt.utils.usb import usb_inventory_scope

from middlewared.api.base.handler.accept import validate_model
from middlewared.service_exception import ValidationErrors


if TYPE_CHECKING:
    from truenas_pylibvirt.device.base import Device
    from .delegate import DeviceDelegate


class DeviceAdapter:

    def __init__(self, device: Device, data: dict[str, Any]):
        self.pylibvirt_device = device
        self.delegate: DeviceDelegate = device.device_delegate
        self.data = data

    def validate(
        self, old: dict[str, Any] | None = None, instance: dict[str, Any] | None = None, update: bool = True
    ) -> None:
        # The scope is lazy, so a validation that never touches USB does not scan udev, while one
        # that does gets a single snapshot shared by every lookup below.
        with usb_inventory_scope():
            verrors = ValidationErrors()

            dump = validate_model(self.delegate.schema_model, self.data['attributes'])
            self.data['attributes'] = dump

            device_errors = self.pylibvirt_device.validate()
            for field, error in device_errors:
                verrors.add(f'attributes.{field}', error)

            self.delegate.validate_middleware(self.data, verrors, old, instance, update)

            verrors.check()
