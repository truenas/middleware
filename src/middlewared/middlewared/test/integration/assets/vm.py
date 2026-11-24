import contextlib

from middlewared.test.integration.utils import call, mock


@contextlib.contextmanager
def vm(data=None):
    # `vm.create` rejects hosts without KVM. The VM record itself needs no KVM, and API-level tests
    # only need the record.
    with mock("vm.supports_virtualization", return_value=True):
        instance = call("vm.create", {"name": "test", "memory": 512, **(data or {})})

    try:
        yield instance
    finally:
        call("vm.delete", instance["id"], {"force": True})


@contextlib.contextmanager
def vm_device(vm_id, attributes, **kwargs):
    device = call("vm.device.create", {"vm": vm_id, "attributes": attributes, **kwargs})

    try:
        yield device
    finally:
        call("vm.device.delete", device["id"])
