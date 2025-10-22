from truenas_pylibvirt.device import (
    Device, CDROMDevice, DisplayDevice, DisplayDeviceType, FilesystemDevice, NICDevice, NICDeviceType, NICDeviceModel,
    PCIDevice, DiskStorageDevice, RawStorageDevice, StorageDeviceType, StorageDeviceIoType, USBDevice
)

from middlewared.plugins.zfs_.utils import zvol_name_to_path

from .delegate import DeviceDelegate


def get_device(device: dict, delegate: DeviceDelegate) -> Device:
    match device['attributes']['dtype']:
        case 'DISK':
            return DiskStorageDevice(
                type_=StorageDeviceType(device['attributes']['type']),
                logical_sectorsize=device['attributes']['logical_sectorsize'],
                physical_sectorsize=device['attributes']['physical_sectorsize'],
                iotype=StorageDeviceIoType(device['attributes']['iotype']),
                serial=device['attributes']['serial'],
                path=device['attributes'].get('path') or zvol_name_to_path(device['attributes']['zvol_name']),
                device_delegate=delegate,
            )
        case 'RAW':
            return RawStorageDevice(
                type_=StorageDeviceType(device['attributes']['type']),
                logical_sectorsize=device['attributes']['logical_sectorsize'],
                physical_sectorsize=device['attributes']['physical_sectorsize'],
                iotype=StorageDeviceIoType(device['attributes']['iotype']),
                serial=device['attributes']['serial'],
                path=device['attributes'].get('path'),
                device_delegate=delegate,
            )
        case 'NIC':
            nic_attach = device['attributes']['nic_attach']
            if nic_attach and nic_attach.startswith('br'):
                type_ = NICDeviceType.BRIDGE
            else:
                type_ = NICDeviceType.DIRECT

            return NICDevice(
                type_=type_,
                source=device['attributes']['nic_attach'],
                model=NICDeviceModel(device['attributes']['type']),
                mac=device['attributes']['mac'],
                trust_guest_rx_filters=device['attributes']['trust_guest_rx_filters'],
                device_delegate=delegate,
            )
        case 'PCI':
            domain, bus, slot, function = device['attributes']['pptdev'].split('_')[1:]
            return PCIDevice(
                domain=domain,
                bus=bus,
                slot=slot,
                function=function,
                pci_device=device['attributes']['pptdev'],
                device_delegate=delegate,
            )
        case 'USB':
            return USBDevice(
                vendor_id=device['attributes']['usb']['vendor_id'] if device['attributes']['usb'] else None,
                product_id=device['attributes']['usb']['product_id'] if device['attributes']['usb'] else None,
                device=device['attributes']['device'],
                controller_type=device['attributes']['controller_type'],
                device_delegate=delegate,
            )
        case 'DISPLAY':
            return DisplayDevice(
                type_=DisplayDeviceType(device['attributes']['type']),
                resolution=device['attributes']['resolution'],
                port=device['attributes']['port'],
                web_port=device['attributes']['web_port'],
                bind=device['attributes']['bind'],
                wait=device['attributes']['wait'],
                password=device['attributes']['password'],
                web=device['attributes']['web'],
                device_delegate=delegate,
            )
        case 'CDROM':
            return CDROMDevice(
                path=device['attributes']['path'],
                device_delegate=delegate,
            )
        case 'FILESYSTEM':
            return FilesystemDevice(
                target=device['attributes']['target'],
                source=device['attributes']['source'],
                device_delegate=delegate,
            )
        case _:
            raise ValueError(f'Unknown device type {device["attributes"]["dtype"]!r}')
