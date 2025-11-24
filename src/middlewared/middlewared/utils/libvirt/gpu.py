from middlewared.service import ValidationErrors

from .delegate import DeviceDelegate


class GPUDelegate(DeviceDelegate):

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        instance: dict | None = None,
        update: bool = True,
    ) -> None:
        if self.middleware.call_sync('system.is_ha_capable'):
            verrors.add('attribute.pci_address', 'HA capable systems do not support GPU devices')

        pci_addr = device['attributes']['pci_address']
        gpu_type = device['attributes']['gpu_type']
        gpu = next((
            g for g in self.middleware.call_sync('device.get_gpus')
            if g['vendor'] == gpu_type and g['addr']['pci_slot'] == pci_addr
        ), None)
        if gpu is None:
            verrors.add(
                'attribute.gpu_type', f'Unable to locate {gpu_type!r} GPU at {pci_addr!r} pci slot'
            )
        elif gpu['available_to_host'] is False:
            verrors.add(
                'attribute.pci_address',
                'GPU is not available to host for consumption'
            )

        if gpu_type == 'NVIDIA' and self.middleware.call_sync('system.advanced.config')['nvidia'] is False:
            verrors.add(
                'attribute.gpu_type',
                'NVIDIA drivers must be enabled in system advanced settings before using nvidia gpu for containers'
            )
