from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .adapter import DeviceAdapter
from .factory_utils import get_device


if TYPE_CHECKING:
    from middlewared.main import Middleware
    from truenas_pylibvirt.device.base import Device
    from .delegate import DeviceDelegate


class DeviceFactory:

    def __init__(self, middleware: Middleware) -> None:
        self._mapping: dict[str, tuple[type[Device], type[DeviceDelegate]]] = {}
        self.middleware = middleware

    def register(self, key: str, device: type[Device], delegate: type[DeviceDelegate]) -> None:
        self._mapping[key] = device, delegate

    def get_items(self) -> dict[str, tuple[type[Device], type[DeviceDelegate]]]:
        return self._mapping

    def get_device(self, device_data: dict[str, Any]) -> Device:
        return get_device(device_data, self._mapping[device_data['attributes']['dtype']][1](
            self.middleware, device_data.get('id'),
        ))

    def get_device_adapter(self, device_data: dict[str, Any]) -> DeviceAdapter:
        device = get_device(device_data, self._mapping[device_data['attributes']['dtype']][1](
            self.middleware, device_data.get('id'),
        ))
        return DeviceAdapter(device, device_data)
