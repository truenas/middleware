import logging
from typing import Any
from xml.etree import ElementTree

import pytest

from middlewared.api.current import VMEntry
from middlewared.plugins.vm.lifecycle import pylibvirt_vm
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service.context import ServiceContext


def make_vm_entry(**overrides: Any) -> VMEntry:
    defaults: dict[str, Any] = dict(
        id=1,
        name="testvm",
        uuid="2f9a4a5f-0f7f-4d1e-9c3a-7c9f3b5d2e11",
        memory=1024,
        devices=[],
        display_available=False,
        status={"state": "STOPPED", "pid": None, "domain_state": None},
    )
    return VMEntry(**(defaults | overrides))


def clock_xml(vm: VMEntry) -> str:
    context = ServiceContext(Middleware(), logging.getLogger("test"))
    # `xml_generator` takes a container-only context, and `VmDomain.run()` yields nothing, so
    # production passes `None` here for VMs too.
    generator = pylibvirt_vm(context, vm).xml_generator(None)
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
    vm = make_vm_entry(time=time, hyperv_enlightenments=hyperv_enlightenments)

    assert clock_xml(vm) == expected_xml
