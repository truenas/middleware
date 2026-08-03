from unittest.mock import Mock
from xml.etree import ElementTree

import pytest

from middlewared.plugins.vm.vm_lifecycle import VMService


def make_vm(**overrides):
    vm = {
        "id": 1,
        "uuid": "2f9a4a5f-0f7f-4d1e-9c3a-7c9f3b5d2e11",
        "name": "testvm",
        "description": "",
        "vcpus": 1,
        "cores": 1,
        "threads": 1,
        "cpuset": None,
        "nodeset": None,
        "memory": 1024,
        "min_memory": None,
        "time": "LOCAL",
        "shutdown_timeout": 90,
        "devices": [],
        "arch_type": None,
        "machine_type": None,
        "bootloader": "UEFI",
        "bootloader_ovmf": "OVMF_CODE.fd",
        "cpu_mode": "CUSTOM",
        "cpu_model": None,
        "enable_cpu_topology_extension": False,
        "pin_vcpus": False,
        "ensure_display_device": True,
        "hyperv_enlightenments": False,
        "trusted_platform_module": False,
        "hide_from_msr": False,
        "enable_secure_boot": False,
        "command_line_args": "",
        "suspend_on_snapshot": True,
    }
    return vm | overrides


def clock_xml(vm):
    service = VMService.__new__(VMService)
    service.middleware = Mock()
    # `xml_generator` takes a container-only context, and `VmDomain.run()` yields nothing, so
    # production passes `None` here for VMs too.
    generator = service.pylibvirt_vm(vm).xml_generator(None)
    return ElementTree.tostring(generator._clock_xml()).decode().strip()


@pytest.mark.parametrize(
    "time,hyperv_enlightenments,expected_xml",
    [
        ("LOCAL", False, '<clock offset="localtime" />'),
        ("LOCAL", True, '<clock offset="localtime"><timer name="hypervclock" present="yes" /></clock>'),
        ("UTC", False, '<clock offset="utc" />'),
        ("UTC", True, '<clock offset="utc"><timer name="hypervclock" present="yes" /></clock>'),
    ],
)
def test_clock_xml(time, hyperv_enlightenments, expected_xml):
    vm = make_vm(time=time, hyperv_enlightenments=hyperv_enlightenments)

    assert clock_xml(vm) == expected_xml
