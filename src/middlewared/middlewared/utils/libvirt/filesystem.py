from typing import Any

from middlewared.service_exception import ValidationErrors

from .delegate import DeviceDelegate
from .utils import device_uniqueness_check


class FilesystemDelegate(DeviceDelegate):

    def validate_middleware(
        self,
        device: dict[str, Any],
        verrors: ValidationErrors,
        old: dict[str, Any] | None = None,
        instance: dict[str, Any] | None = None,
        update: bool = True,
    ) -> None:
        path = device['attributes']['source']
        self.middleware.call_sync('container.device.validate_path_field', verrors, 'attributes.path', path)
        if instance is not None and not device_uniqueness_check(
            device, instance, ('DISK', 'RAW', 'CDROM', 'FILESYSTEM'),
        ):
            verrors.add(
                'attributes.target',
                f'{instance["name"]} has {device["attributes"]["target"]!r} target already configured'
            )
        super().validate_middleware(device, verrors, old, instance, update)
