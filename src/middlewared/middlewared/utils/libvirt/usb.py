from typing import Any

from middlewared.service_exception import ValidationErrors

from .delegate import DeviceDelegate
from .utils import _extract_identity, device_uniqueness_check


class USBDelegate(DeviceDelegate):

    def validate_middleware(
        self,
        device: dict[str, Any],
        verrors: ValidationErrors,
        old: dict[str, Any] | None = None,
        instance: dict[str, Any] | None = None,
        update: bool = True,
    ) -> None:
        if self.middleware.call_sync('system.is_ha_capable'):
            verrors.add('attributes.usb', 'HA capable systems do not support USB passthrough.')

        if instance is not None and not device_uniqueness_check(device, instance, 'USB'):
            identity = _extract_identity(device)
            verrors.add(
                'attributes.port' if device['attributes'].get('port') else 'attributes.usb',
                f'{instance["name"]} already has USB device {identity!r} configured'
            )
