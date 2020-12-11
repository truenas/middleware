from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class PCIDeviceUnavailableAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.SHARING
    title = 'Unable to Configure PCI Device For VM'
    text = '%(pci)s device cannot be used with VM %(vm_name)s as it is not configured to use vfio-pci kernel module.'

    async def create(self, args):
        return Alert(PCIDeviceUnavailableAlertClass, args, key=args['pci'])

    async def delete(self, alerts, query):
        return list(filter(lambda alert: alert.key != f'"{query}"', alerts))
