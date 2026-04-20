import pytest

from middlewared.utils.libvirt.utils import _extract_identity, device_uniqueness_check


# Map used by the mock: (vendor_id, product_id) -> libvirt device name
_MOCK_USB_IDS = {
    ('0x1d6b', '0x0002'): 'usb_1_1',
    ('0x0781', '0x5583'): 'usb_2_3',
    ('0x1234', '0x5678'): 'usb_3_1_4',
}


def _mock_find_usb_device_by_ids(vendor_id: str, product_id: str) -> str | None:
    return _MOCK_USB_IDS.get((vendor_id, product_id))


@pytest.fixture(autouse=True)
def mock_find_usb(monkeypatch):
    monkeypatch.setattr(
        'middlewared.utils.libvirt.utils.find_usb_device_by_ids',
        _mock_find_usb_device_by_ids,
    )


# ---------------------------------------------------------------------------
# Realistic VM/container instance fixtures
# ---------------------------------------------------------------------------

VM_INSTANCE = {
    'name': 'test-vm-01',
    'status': {'state': 'STOPPED'},
    'devices': [
        {
            'id': 1,
            'attributes': {
                'dtype': 'DISK',
                'path': '/dev/zvol/tank/vm-disks/boot',
                'type': 'VIRTIO',
                'create_zvol': False,
            },
            'vm': 10,
            'order': 1001,
        },
        {
            'id': 2,
            'attributes': {
                'dtype': 'CDROM',
                'path': '/mnt/tank/iso/ubuntu-24.04.iso',
            },
            'vm': 10,
            'order': 1002,
        },
        {
            'id': 3,
            'attributes': {
                'dtype': 'NIC',
                'nic_attach': 'br0',
                'mac': '00:a0:98:61:f2:a0',
                'type': 'VIRTIO',
                'trust_guest_rx_filters': False,
            },
            'vm': 10,
            'order': 1003,
        },
        {
            'id': 4,
            'attributes': {
                'dtype': 'PCI',
                'pptdev': 'pci_0000_01_00_0',
            },
            'vm': 10,
            'order': 1004,
        },
        {
            'id': 5,
            'attributes': {
                'dtype': 'USB',
                'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'},
                'device': None,
                'controller_type': 'nec-xhci',
            },
            'vm': 10,
            'order': 1005,
        },
        {
            'id': 6,
            'attributes': {
                'dtype': 'USB',
                'usb': None,
                'device': 'usb_3_1_4',
                'controller_type': 'nec-xhci',
            },
            'vm': 10,
            'order': 1006,
        },
        {
            'id': 7,
            'attributes': {
                'dtype': 'DISPLAY',
                'type': 'SPICE',
                'port': 5900,
                'web_port': 5901,
                'bind': '0.0.0.0',
                'resolution': '1024x768',
            },
            'vm': 10,
            'order': 1007,
        },
    ],
}

CONTAINER_INSTANCE = {
    'name': 'test-container-01',
    'status': {'state': 'RUNNING'},
    'devices': [
        {
            'id': 10,
            'attributes': {
                'dtype': 'FILESYSTEM',
                'source': '/mnt/tank/shares/media',
                'target': '/media',
            },
            'container': 20,
        },
        {
            'id': 11,
            'attributes': {
                'dtype': 'GPU',
                'gpu_type': 'NVIDIA',
                'pci_address': '0000:41:00.0',
            },
            'container': 20,
        },
        {
            'id': 12,
            'attributes': {
                'dtype': 'NIC',
                'nic_attach': 'br0',
                'mac': '00:a0:98:3c:dd:10',
                'type': 'VIRTIO',
                'trust_guest_rx_filters': False,
            },
            'container': 20,
        },
        {
            'id': 13,
            'attributes': {
                'dtype': 'USB',
                'usb': {'vendor_id': '0x0781', 'product_id': '0x5583'},
                'device': None,
            },
            'container': 20,
        },
    ],
}


# ===========================================================================
# _extract_identity
# ===========================================================================

def test_extract_identity_pci():
    device = {'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}}
    assert _extract_identity(device) == 'pci_0000_01_00_0'


def test_extract_identity_gpu():
    device = {'attributes': {'dtype': 'GPU', 'pci_address': '0000:41:00.0'}}
    assert _extract_identity(device) == '0000:41:00.0'


def test_extract_identity_nic_mac():
    device = {'attributes': {'dtype': 'NIC', 'mac': '00:a0:98:61:f2:a0'}}
    assert _extract_identity(device) == '00:a0:98:61:f2:a0'


def test_extract_identity_nic_no_mac():
    device = {'attributes': {'dtype': 'NIC', 'mac': None}}
    assert _extract_identity(device) is None


def test_extract_identity_disk_path():
    device = {'attributes': {'dtype': 'DISK', 'path': '/dev/zvol/tank/disk1'}}
    assert _extract_identity(device) == '/dev/zvol/tank/disk1'


def test_extract_identity_cdrom_path():
    device = {'attributes': {'dtype': 'CDROM', 'path': '/mnt/tank/iso/test.iso'}}
    assert _extract_identity(device) == '/mnt/tank/iso/test.iso'


def test_extract_identity_filesystem_target():
    device = {'attributes': {'dtype': 'FILESYSTEM', 'target': '/media', 'source': '/mnt/tank/shares'}}
    assert _extract_identity(device) == '/media'


def test_extract_identity_usb_device_path_priority():
    """Host device path should take priority over vendor:product."""
    device = {'attributes': {
        'dtype': 'USB', 'device': 'usb_3_1_4',
        'usb': {'vendor_id': '0x1234', 'product_id': '0x5678'},
    }}
    assert _extract_identity(device) == 'usb_3_1_4'


def test_extract_identity_usb_vendor_product():
    """Vendor:product should resolve to the device path via find_usb_device_by_ids."""
    device = {'attributes': {
        'dtype': 'USB', 'device': None,
        'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'},
    }}
    assert _extract_identity(device) == 'usb_1_1'


def test_extract_identity_usb_no_identity():
    device = {'attributes': {'dtype': 'USB', 'device': None, 'usb': None}}
    assert _extract_identity(device) is None


def test_extract_identity_usb_partial_attrs():
    """Only vendor_id without product_id should return None."""
    device = {'attributes': {
        'dtype': 'USB', 'device': None,
        'usb': {'vendor_id': '0x1234', 'product_id': None},
    }}
    assert _extract_identity(device) is None


def test_extract_identity_usb_vendor_product_not_on_system():
    """When vendor:product cannot be resolved to a device path, returns None."""
    device = {'attributes': {
        'dtype': 'USB', 'device': None,
        'usb': {'vendor_id': '0xffff', 'product_id': '0xffff'},
    }}
    assert _extract_identity(device) is None


def test_extract_identity_unknown_dtype():
    device = {'attributes': {'dtype': 'UNKNOWN_TYPE'}}
    assert _extract_identity(device) is None


# ===========================================================================
# Core four-state logic
# ===========================================================================

def test_unique_device_passes():
    """A PCI device with a new pptdev not already on the VM should pass."""
    new_device = {'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_99_00_0'}}
    assert device_uniqueness_check(new_device, VM_INSTANCE, 'PCI') is True


def test_empty_device_list_passes():
    """Any device should pass when the instance has no devices."""
    new_device = {'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}}
    instance = {'name': 'empty-vm', 'devices': []}
    assert device_uniqueness_check(new_device, instance, 'PCI') is True


def test_new_device_duplicating_existing_fails():
    """Adding a new PCI device (no id) that duplicates existing id=4 should fail."""
    new_device = {'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}}
    assert device_uniqueness_check(new_device, VM_INSTANCE, 'PCI') is False


def test_batch_creation_both_new_passes():
    """During instance creation, two new devices (neither has id) should pass."""
    new_device = {'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}}
    batch_instance = {
        'name': 'new-vm',
        'devices': [
            {'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}},
        ],
    }
    assert device_uniqueness_check(new_device, batch_instance, 'PCI') is True


def test_update_same_device_passes():
    """Updating device id=4 to the same pptdev it already has should pass."""
    updated = {'id': 4, 'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}}
    assert device_uniqueness_check(updated, VM_INSTANCE, 'PCI') is True


def test_update_colliding_with_different_device_fails():
    """Updating one device to match another existing device's identity should fail."""
    instance = {
        'name': 'vm-two-pci',
        'devices': [
            {'id': 1, 'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}},
            {'id': 2, 'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_02_00_0'}},
        ],
    }
    updated = {'id': 2, 'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}}
    assert device_uniqueness_check(updated, instance, 'PCI') is False


def test_multiple_matches_misconfigured_fails():
    """Multiple existing devices with identical identity means misconfiguration."""
    bad_instance = {
        'name': 'broken-vm',
        'devices': [
            {'id': 1, 'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}},
            {'id': 2, 'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}},
        ],
    }
    updated = {'id': 1, 'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}}
    assert device_uniqueness_check(updated, bad_instance, 'PCI') is False


def test_none_identity_always_passes():
    """When identity is None (USB controller-only), the check is skipped."""
    new_usb = {'attributes': {'dtype': 'USB', 'usb': None, 'device': None}}
    assert device_uniqueness_check(new_usb, VM_INSTANCE, 'USB') is True


# ===========================================================================
# dtype filtering
# ===========================================================================

def test_different_dtype_no_collision():
    """A PCI device should not collide with a DISK even if the value matches."""
    new_pci = {'attributes': {'dtype': 'PCI', 'pptdev': '/dev/zvol/tank/vm-disks/boot'}}
    assert device_uniqueness_check(new_pci, VM_INSTANCE, 'PCI') is True


def test_dtype_tuple_cross_type_collision():
    """RAW with same path as existing DISK should collide within the storage dtype tuple."""
    new_raw = {'attributes': {'dtype': 'RAW', 'path': '/dev/zvol/tank/vm-disks/boot'}}
    assert device_uniqueness_check(
        new_raw, VM_INSTANCE, ('DISK', 'RAW', 'CDROM', 'FILESYSTEM'),
    ) is False


def test_dtype_string_auto_converted_to_tuple():
    """Passing dtype as a string should work the same as a single-element tuple."""
    new_gpu = {'attributes': {'dtype': 'GPU', 'pci_address': '0000:41:00.0'}}
    assert device_uniqueness_check(new_gpu, CONTAINER_INSTANCE, 'GPU') is False


# ===========================================================================
# PCI device uniqueness against VM_INSTANCE
# ===========================================================================

def test_vm_pci_duplicate():
    """Adding the same pptdev already on VM_INSTANCE (id=4) should fail."""
    new_pci = {'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_01_00_0'}}
    assert device_uniqueness_check(new_pci, VM_INSTANCE, 'PCI') is False


def test_vm_pci_different_device():
    """Adding a different pptdev to VM_INSTANCE should pass."""
    new_pci = {'attributes': {'dtype': 'PCI', 'pptdev': 'pci_0000_03_00_0'}}
    assert device_uniqueness_check(new_pci, VM_INSTANCE, 'PCI') is True


# ===========================================================================
# USB device uniqueness against VM_INSTANCE
# ===========================================================================

def test_vm_usb_duplicate_vendor_product():
    """Adding USB with same vendor:product as id=5 on VM_INSTANCE should fail."""
    new_usb = {'attributes': {
        'dtype': 'USB', 'device': None,
        'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'},
    }}
    assert device_uniqueness_check(new_usb, VM_INSTANCE, 'USB') is False


def test_vm_usb_duplicate_device_path():
    """Adding USB with same device path as id=6 on VM_INSTANCE should fail."""
    new_usb = {'attributes': {'dtype': 'USB', 'device': 'usb_3_1_4', 'usb': None}}
    assert device_uniqueness_check(new_usb, VM_INSTANCE, 'USB') is False


def test_vm_usb_different_device_passes():
    """Adding a USB with a completely different identity should pass."""
    new_usb = {'attributes': {'dtype': 'USB', 'device': 'usb_5_2_0', 'usb': None}}
    assert device_uniqueness_check(new_usb, VM_INSTANCE, 'USB') is True


def test_vm_usb_cross_format_vendor_product_duplicates_device_path():
    """Adding USB by vendor:product that resolves to same device path as existing entry should fail."""
    # Instance has id=6 with device='usb_3_1_4'
    # Mock maps ('0x1234', '0x5678') -> 'usb_3_1_4'
    new_usb = {'attributes': {
        'dtype': 'USB', 'device': None,
        'usb': {'vendor_id': '0x1234', 'product_id': '0x5678'},
    }}
    assert device_uniqueness_check(new_usb, VM_INSTANCE, 'USB') is False


def test_vm_usb_cross_format_device_path_duplicates_vendor_product():
    """Adding USB by device path that matches resolved path of existing vendor:product entry should fail."""
    # Instance has id=5 with vendor:product '0x1d6b':'0x0002' -> resolves to 'usb_1_1'
    new_usb = {'attributes': {'dtype': 'USB', 'device': 'usb_1_1', 'usb': None}}
    assert device_uniqueness_check(new_usb, VM_INSTANCE, 'USB') is False


def test_vm_usb_different_device_path_no_collision():
    """USB by device path should not collide when it's a genuinely different device."""
    new_usb = {'attributes': {'dtype': 'USB', 'device': 'usb_9_9_9', 'usb': None}}
    assert device_uniqueness_check(new_usb, VM_INSTANCE, 'USB') is True


def test_vm_usb_controller_only_no_collision():
    """USB controller-only devices (no identity) should never collide."""
    new_usb = {'attributes': {'dtype': 'USB', 'device': None, 'usb': None}}
    assert device_uniqueness_check(new_usb, VM_INSTANCE, 'USB') is True


# ===========================================================================
# GPU uniqueness against CONTAINER_INSTANCE
# ===========================================================================

def test_container_gpu_duplicate():
    """Adding same pci_address GPU already on CONTAINER_INSTANCE (id=11) should fail."""
    new_gpu = {'attributes': {
        'dtype': 'GPU', 'pci_address': '0000:41:00.0', 'gpu_type': 'NVIDIA',
    }}
    assert device_uniqueness_check(new_gpu, CONTAINER_INSTANCE, 'GPU') is False


def test_container_gpu_different():
    """Adding a different pci_address GPU should pass."""
    new_gpu = {'attributes': {
        'dtype': 'GPU', 'pci_address': '0000:82:00.0', 'gpu_type': 'AMD',
    }}
    assert device_uniqueness_check(new_gpu, CONTAINER_INSTANCE, 'GPU') is True


def test_container_gpu_update_same_device():
    """Updating GPU id=11 to the same pci_address should pass."""
    updated = {'id': 11, 'attributes': {
        'dtype': 'GPU', 'pci_address': '0000:41:00.0', 'gpu_type': 'NVIDIA',
    }}
    assert device_uniqueness_check(updated, CONTAINER_INSTANCE, 'GPU') is True


# ===========================================================================
# NIC MAC uniqueness
# ===========================================================================

def test_vm_nic_duplicate_mac():
    """Adding a NIC with same MAC as id=3 on VM_INSTANCE should fail."""
    new_nic = {'attributes': {
        'dtype': 'NIC', 'mac': '00:a0:98:61:f2:a0', 'nic_attach': 'br1',
    }}
    assert device_uniqueness_check(new_nic, VM_INSTANCE, 'NIC') is False


def test_vm_nic_same_interface_different_mac():
    """Multiple NICs on the same nic_attach but different MACs should pass."""
    new_nic = {'attributes': {
        'dtype': 'NIC', 'mac': '00:a0:98:aa:bb:cc', 'nic_attach': 'br0',
    }}
    assert device_uniqueness_check(new_nic, VM_INSTANCE, 'NIC') is True


def test_container_nic_duplicate_mac():
    """Adding a NIC with same MAC as id=12 on CONTAINER_INSTANCE should fail."""
    new_nic = {'attributes': {
        'dtype': 'NIC', 'mac': '00:a0:98:3c:dd:10', 'nic_attach': 'br0',
    }}
    assert device_uniqueness_check(new_nic, CONTAINER_INSTANCE, 'NIC') is False


def test_nic_no_mac_skips_check():
    """NIC with no MAC (None) should not collide."""
    new_nic = {'attributes': {'dtype': 'NIC', 'mac': None, 'nic_attach': 'br0'}}
    assert device_uniqueness_check(new_nic, VM_INSTANCE, 'NIC') is True


# ===========================================================================
# Container USB uniqueness against CONTAINER_INSTANCE
# ===========================================================================

def test_container_usb_duplicate_vendor_product():
    """Adding USB with same vendor:product as id=13 on CONTAINER_INSTANCE should fail."""
    new_usb = {'attributes': {
        'dtype': 'USB', 'device': None,
        'usb': {'vendor_id': '0x0781', 'product_id': '0x5583'},
    }}
    assert device_uniqueness_check(new_usb, CONTAINER_INSTANCE, 'USB') is False


def test_container_usb_different_vendor_product():
    """Adding USB with different vendor:product should pass."""
    new_usb = {'attributes': {
        'dtype': 'USB', 'device': None,
        'usb': {'vendor_id': '0x1234', 'product_id': '0x0001'},
    }}
    assert device_uniqueness_check(new_usb, CONTAINER_INSTANCE, 'USB') is True


# ===========================================================================
# Storage device backward compat against VM_INSTANCE
# ===========================================================================

def test_vm_disk_duplicate_path():
    """Adding a DISK with same path as id=1 on VM_INSTANCE should fail."""
    new_disk = {'attributes': {'dtype': 'DISK', 'path': '/dev/zvol/tank/vm-disks/boot'}}
    assert device_uniqueness_check(
        new_disk, VM_INSTANCE, ('DISK', 'RAW', 'CDROM', 'FILESYSTEM'),
    ) is False


def test_vm_cdrom_duplicate_path():
    """Adding a CDROM with same path as id=2 on VM_INSTANCE should fail."""
    new_cdrom = {'attributes': {
        'dtype': 'CDROM', 'path': '/mnt/tank/iso/ubuntu-24.04.iso',
    }}
    assert device_uniqueness_check(
        new_cdrom, VM_INSTANCE, ('DISK', 'RAW', 'CDROM', 'FILESYSTEM'),
    ) is False


def test_vm_disk_unique_path():
    """Adding a DISK with a new path should pass."""
    new_disk = {'attributes': {'dtype': 'DISK', 'path': '/dev/zvol/tank/vm-disks/data'}}
    assert device_uniqueness_check(
        new_disk, VM_INSTANCE, ('DISK', 'RAW', 'CDROM', 'FILESYSTEM'),
    ) is True


def test_container_filesystem_duplicate_target():
    """Adding a FILESYSTEM with same target as id=10 should fail."""
    new_fs = {'attributes': {
        'dtype': 'FILESYSTEM', 'source': '/mnt/tank/other', 'target': '/media',
    }}
    assert device_uniqueness_check(
        new_fs, CONTAINER_INSTANCE, ('DISK', 'RAW', 'CDROM', 'FILESYSTEM'),
    ) is False
