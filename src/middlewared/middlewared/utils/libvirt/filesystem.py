from typing import Any

from middlewared.service_exception import ValidationErrors

from .delegate import DeviceDelegate
from .utils import disk_uniqueness_integrity_check


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
        if instance is not None and not disk_uniqueness_integrity_check(device, instance):
            verrors.add(
                'attributes.target',
                f'{instance["name"]} has {device["attributes"]["target"]!r} target already configured'
            )
        super().validate_middleware(device, verrors, old, instance, update)
