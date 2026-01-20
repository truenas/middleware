import pyudev


def list_usb_devices() -> dict[str, dict[str, str | int]]:
    devices = {}
    context = pyudev.Context()
    for device in context.list_devices(subsystem='usb', DEVTYPE='usb_device'):
        busnum = device.attributes.get('busnum')
        devnum = device.attributes.get('devnum')

        if busnum is None or devnum is None:
            continue

        bus = int(busnum)
        address = int(devnum)
        name = f'usb_{bus}_{address}'

        vendor_id = device.attributes.get('idVendor')
        product_id = device.attributes.get('idProduct')

        if vendor_id is None or product_id is None:
            continue

        vendor_id = vendor_id.decode()
        product_id = product_id.decode()

        # Attempt to get product and manufacturer from udev properties
        props = device.properties
        product = props.get('ID_MODEL_FROM_DATABASE') or props.get('ID_MODEL') or 'Unknown product'
        manufacturer = props.get('ID_VENDOR_FROM_DATABASE') or props.get('ID_VENDOR') or 'Unknown manufacturer'

        devices[name] = {
            'vendor_id': vendor_id,
            'product_id': product_id,
            'bus': bus,
            'dev': address,
            'product': product,
            'manufacturer': manufacturer,
        }
    return devices
