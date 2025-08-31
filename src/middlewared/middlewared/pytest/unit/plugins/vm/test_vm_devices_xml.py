import pytest

from unittest.mock import patch
from xml.etree import ElementTree as etree

from middlewared.plugins.vm.devices import CDROM, DISK, NIC, RAW, DISPLAY
from middlewared.plugins.vm.supervisor.domain_xml import devices_xml
from middlewared.pytest.unit.middleware import Middleware

GUEST_CHANEL = '<channel type="unix"><target type="virtio" name="org.qemu.guest_agent.0" /></channel>'


@pytest.mark.parametrize('vm_data,expected_xml', [
    ({'ensure_display_device': False, 'trusted_platform_module': False, 'devices': [], 'min_memory': None},
     f'<devices>{GUEST_CHANEL}<serial type="pty" /></devices>'),
    ({'ensure_display_device': True, 'trusted_platform_module': False, 'devices': [], 'min_memory': None},
     f'<devices><video />{GUEST_CHANEL}<serial type="pty" /></devices>'),
])
def test_basic_devices_xml(vm_data, expected_xml):
    assert etree.tostring(devices_xml(vm_data, {'devices': []})).decode().strip() == expected_xml


@pytest.mark.parametrize('vm_data,expected_xml', [
    ({'ensure_display_device': False, 'trusted_platform_module': False, 'min_memory': None, 'devices': [{
        'attributes': {'path': '/mnt/tank/disk.iso', 'dtype': 'CDROM'},
    }]}, '<devices><disk type="file" device="cdrom"><driver name="qemu" type="raw" />'
         '<source file="/mnt/tank/disk.iso" /><target dev="sda" bus="sata" /><boot order="1" />'
         f'</disk>{GUEST_CHANEL}<serial type="pty" /></devices>'
    ),
])
def test_cdrom_xml(vm_data, expected_xml):
    m = Middleware()
    with patch('middlewared.plugins.vm.devices.cdrom.CDROM.is_available') as mock:
        mock.return_value = True
        assert etree.tostring(devices_xml(
            vm_data, {'devices': [CDROM(device, m) for device in vm_data['devices']]})
        ).decode().strip() == expected_xml


@pytest.mark.parametrize('vm_data,expected_xml', [
    ({'ensure_display_device': False, 'trusted_platform_module': False, 'min_memory': None, 'devices': [{
        'attributes': {
            'dtype': 'DISPLAY',
            'bind': '0.0.0.0',
            'password': '',
            'web': True,
            'type': 'SPICE',
            'resolution': '1024x768',
            'port': 5912,
            'web_port': 5913,
            'wait': False,
        },
    }]}, '<devices><graphics type="spice" port="5912"><listen type="address" address="0.0.0.0" /></graphics>'
         '<controller type="usb" model="nec-xhci" /><input type="tablet" bus="usb" /><video>'
         '<model type="qxl"><resolution x="1024" y="768" /></model></video><channel type="spicevmc">'
         f'<target type="virtio" name="com.redhat.spice.0" /></channel>{GUEST_CHANEL}<serial type="pty" /></devices>'
    ),
    ({'ensure_display_device': False, 'trusted_platform_module': False, 'min_memory': None, 'devices': [{
        'attributes': {
            'dtype': 'DISPLAY',
            'bind': '0.0.0.0',
            'password': '',
            'web': True,
            'type': 'SPICE',
            'resolution': '1920x1080',
            'port': 5912,
            'web_port': 5913,
            'wait': False,
            'vgamem': 65536,  # 64MB
        },
    }]}, '<devices><graphics type="spice" port="5912"><listen type="address" address="0.0.0.0" /></graphics>'
         '<controller type="usb" model="nec-xhci" /><input type="tablet" bus="usb" /><video>'
         '<model type="qxl" vgamem="65536"><resolution x="1920" y="1080" /></model></video><channel type="spicevmc">'
         f'<target type="virtio" name="com.redhat.spice.0" /></channel>{GUEST_CHANEL}<serial type="pty" /></devices>'
    ),
    ({'ensure_display_device': False, 'trusted_platform_module': False, 'min_memory': None, 'devices': [{
        'attributes': {
            'dtype': 'DISPLAY',
            'bind': '0.0.0.0',
            'password': '',
            'web': True,
            'type': 'SPICE',
            'resolution': '1920x1080',
            'port': 5912,
            'web_port': 5913,
            'wait': False,
            'vgamem': 65536,  # 64MB
            'ram': 131072,    # 128MB
            'vram': 131072,   # 128MB
        },
    }]}, '<devices><graphics type="spice" port="5912"><listen type="address" address="0.0.0.0" /></graphics>'
         '<controller type="usb" model="nec-xhci" /><input type="tablet" bus="usb" /><video>'
         '<model type="qxl" vgamem="65536" ram="131072" vram="131072"><resolution x="1920" y="1080" /></model></video>'
         f'<channel type="spicevmc"><target type="virtio" name="com.redhat.spice.0" /></channel>{GUEST_CHANEL}'
         '<serial type="pty" /></devices>'
    ),
])
def test_display_xml(vm_data, expected_xml):
    m = Middleware()
    with patch('middlewared.plugins.vm.devices.display.DISPLAY.is_available') as mock:
        mock.return_value = True
        assert etree.tostring(devices_xml(
            vm_data, {'devices': [DISPLAY(device, m) for device in vm_data['devices']]})
        ).decode().strip() == expected_xml


@pytest.mark.parametrize('vm_data,expected_xml', [
    ({'ensure_display_device': False, 'trusted_platform_module': False, 'min_memory': None, 'devices': [{
        'attributes': {
            'type': 'VIRTIO',
            'mac': '00:a0:99:7e:bb:8a',
            'nic_attach': 'br0',
            'trust_guest_rx_filters': False,
            'dtype': 'NIC',
        },
    }]}, '<devices><interface type="bridge"><source bridge="br0" /><model type="virtio" />'
         '<mac address="00:a0:99:7e:bb:8a" /></interface>'
         f'{GUEST_CHANEL}<serial type="pty" /></devices>'
    ),
    ({'ensure_display_device': False, 'trusted_platform_module': False, 'min_memory': None, 'devices': [{
        'attributes': {
            'type': 'VIRTIO',
            'mac': '00:a0:99:7e:bb:8a',
            'nic_attach': 'ens3',
            'trust_guest_rx_filters': False,
            'dtype': 'NIC',
        },
    }]}, '<devices><interface type="direct" trustGuestRxFilters="no"><source dev="ens3" mode="bridge" />'
         '<model type="virtio" /><mac address="00:a0:99:7e:bb:8a" /></interface>'
         f'{GUEST_CHANEL}<serial type="pty" /></devices>'
    ),
    ({'ensure_display_device': False, 'trusted_platform_module': False, 'min_memory': None, 'devices': [{
        'attributes': {
            'type': 'VIRTIO',
            'mac': '00:a0:99:7e:bb:8a',
            'nic_attach': 'ens3',
            'trust_guest_rx_filters': True,
            'dtype': 'NIC',
        },
    }]}, '<devices><interface type="direct" trustGuestRxFilters="yes"><source dev="ens3" mode="bridge" />'
         '<model type="virtio" /><mac address="00:a0:99:7e:bb:8a" /></interface>'
         f'{GUEST_CHANEL}<serial type="pty" /></devices>'
    ),
])
@patch('middlewared.plugins.vm.devices.nic.NIC.is_available', lambda *args: True)
def test_nic_xml(vm_data, expected_xml):

    def setup_nic_attach(self):
        self.nic_attach = vm_data['devices'][0]['attributes']['nic_attach']

    m = Middleware()
    with patch('middlewared.plugins.vm.devices.nic.NIC.setup_nic_attach', setup_nic_attach):
        assert etree.tostring(devices_xml(
            vm_data, {'devices': [NIC(device, m) for device in vm_data['devices']]})
        ).decode().strip() == expected_xml


@pytest.mark.parametrize('vm_data,expected_xml', [
    ({'ensure_display_device': False, 'trusted_platform_module': False, 'min_memory': None, 'devices': [{
        'attributes': {
            'path': '/dev/zvol/pool/boot_1',
            'type': 'AHCI',
            'logical_sectorsize': None,
            'physical_sectorsize': None,
            'iotype': 'THREADS',
            'serial': 'test-serial',
            'dtype': 'DISK',
        },
    }]}, (
        '<devices><disk type="block" device="disk">'
        '<driver name="qemu" type="raw" cache="none" io="threads" discard="unmap" />'
        '<source dev="/dev/zvol/pool/boot_1" /><target bus="sata" dev="sda" />'
        '<serial>test-serial</serial><boot order="1" />'
        f'</disk>{GUEST_CHANEL}<serial type="pty" /></devices>'
    )
    ),
])
def test_disk_xml(vm_data, expected_xml):
    m = Middleware()
    with patch('middlewared.plugins.vm.devices.storage_devices.DISK.is_available') as mock:
        mock.return_value = True
        assert etree.tostring(devices_xml(
            vm_data, {'devices': [DISK(device, m) for device in vm_data['devices']]})
        ).decode().strip() == expected_xml


@pytest.mark.parametrize('vm_data,expected_xml', [
    ({'ensure_display_device': False, 'trusted_platform_module': False, 'min_memory': None, 'devices': [{
        'attributes': {
            'path': '/mnt/tank/somefile',
            'type': 'AHCI',
            'logical_sectorsize': None,
            'physical_sectorsize': None,
            'iotype': 'THREADS',
            'serial': 'test-serial',
            'dtype': 'RAW',
        },
    }]}, (
        '<devices><disk type="file" device="disk">'
        '<driver name="qemu" type="raw" cache="none" io="threads" discard="unmap" />'
        '<source file="/mnt/tank/somefile" /><target bus="sata" dev="sda" />'
        '<serial>test-serial</serial><boot order="1" />'
        f'</disk>{GUEST_CHANEL}<serial type="pty" /></devices>'
    )
    ),
    ({'ensure_display_device': False, 'trusted_platform_module': False, 'min_memory': None, 'devices': [{
        'attributes': {
            'path': '/mnt/tank/somefile',
            'type': 'AHCI',
            'logical_sectorsize': 512,
            'physical_sectorsize': 512,
            'iotype': 'THREADS',
            'serial': 'test-serial',
            'dtype': 'RAW',
        },
    }]}, (
        '<devices><disk type="file" device="disk">'
        '<driver name="qemu" type="raw" cache="none" io="threads" discard="unmap" />'
        '<source file="/mnt/tank/somefile" /><target bus="sata" dev="sda" />'
        '<serial>test-serial</serial><boot order="1" />'
        '<blockio logical_block_size="512" physical_block_size="512" /></disk>'
        f'{GUEST_CHANEL}<serial type="pty" /></devices>'
    )
    ),
])
def test_raw_xml(vm_data, expected_xml):
    m = Middleware()
    with patch('middlewared.plugins.vm.devices.storage_devices.RAW.is_available') as mock:
        mock.return_value = True
        assert etree.tostring(devices_xml(
            vm_data, {'devices': [RAW(device, m) for device in vm_data['devices']]})
        ).decode().strip() == expected_xml
