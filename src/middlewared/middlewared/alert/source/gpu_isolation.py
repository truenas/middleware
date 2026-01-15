from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, SimpleOneShotAlertClass


class InvalidGpuPciIdsAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.SYSTEM
    title = 'Reboot Required: GPU Configuration Updated'
    text = (
        'One or more GPUs previously configured for isolation are no longer present in the system '
        '(PCI IDs: %(pci_ids)s). The isolation configuration has been automatically updated. '
        'Please reboot the system to apply these changes.'
    )
    keys = []
