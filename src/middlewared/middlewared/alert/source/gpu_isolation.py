from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


class InvalidGpuPciIdsAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title='Reboot Required: GPU Configuration Updated',
        text=(
            'One or more GPUs previously configured for isolation are no longer present in the system '
            '(PCI IDs: %(pci_ids)s). The isolation configuration has been automatically updated. '
            'Please reboot the system to apply these changes.'
        ),
        deleted_automatically=False,
        keys=[],
    )
