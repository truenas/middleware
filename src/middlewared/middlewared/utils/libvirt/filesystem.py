from middlewared.service_exception import ValidationErrors

from .delegate import DeviceDelegate


class FilesystemDelegate(DeviceDelegate):

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        instance: dict | None = None,
        update: bool = True,
    ) -> None:
        path = device['attributes']['source']
        self.middleware.call_sync('container.device.validate_path_field', verrors, 'attributes.path', path)
        super().validate_middleware(device, verrors, old, instance, update)
