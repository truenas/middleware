"""Tests for arch-specific VM validation rules (item #8)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from middlewared.api.current import VMCreate, VMFlags
from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import ValidationErrors

VMService = load_compound_service("vm")

_VM_FLAGS = VMFlags(intel_vmx=True, unrestricted_guest=True, amd_rvi=False, amd_asids=False)

_ARCH_CHOICES = {
    "x86_64": {"pc-q35-6.2": "pc-q35-6.2"},
    "i686": {"pc-q35-6.2": "pc-q35-6.2"},
    "i386": {"pc-q35-6.2": "pc-q35-6.2"},
    "aarch64": {"virt-9.2": "virt-9.2"},
}

# Minimal aarch64 VM payload; all x86-incompatible flags off by default.
_AARCH64_BASE = {
    "name": "arm64_vm",
    "description": "",
    "vcpus": 1,
    "memory": 512,
    "min_memory": None,
    "autostart": False,
    "time": "LOCAL",
    "bootloader": "UEFI",
    "bootloader_ovmf": "AAVMF_CODE.fd",
    "cores": 1,
    "threads": 1,
    "hyperv_enlightenments": False,
    "shutdown_timeout": 90,
    "cpu_mode": "CUSTOM",
    "cpu_model": "cortex-a53",
    "cpuset": None,
    "nodeset": None,
    "pin_vcpus": False,
    "hide_from_msr": False,
    "ensure_display_device": True,
    "arch_type": "aarch64",
    "machine_type": None,
    "uuid": "64e31dd7-8c76-4dca-8b4b-0126b8853c5b",
    "command_line_args": "",
    "enable_secure_boot": False,
}


def _make_svc():
    m = Middleware()
    m["system.is_ha_capable"] = lambda *args: False
    m["datastore.query"] = lambda *args, **kwargs: []
    return VMService(m)


@pytest.mark.parametrize(
    "override,rejected_field,fragment",
    [
        (
            {"bootloader": "UEFI_CSM"},
            "vm_create.bootloader",
            "x86-only",
        ),
        (
            {"hyperv_enlightenments": True},
            "vm_create.hyperv_enlightenments",
            "x86-only",
        ),
        (
            {"hide_from_msr": True},
            "vm_create.hide_from_msr",
            "x86-specific",
        ),
    ],
)
@pytest.mark.asyncio
async def test_aarch64_rejects_x86_only_flags(override, rejected_field, fragment):
    vm_svc = _make_svc()
    data = VMCreate(**{**_AARCH64_BASE, **override})

    with (
        patch("middlewared.plugins.vm.crud.vm_flags", return_value=_VM_FLAGS),
        patch("middlewared.plugins.vm.crud.guest_architecture_and_machine_choices", return_value=_ARCH_CHOICES),
        patch("middlewared.plugins.vm.crud.cpu_model_choices", return_value={"cortex-a53": "cortex-a53"}),
    ):
        verrors = ValidationErrors()
        await vm_svc._svc_part.validate(verrors, "vm_create", data)

    matching = [e for e in verrors.errors if e.attribute == rejected_field]
    assert matching, f"Expected error on {rejected_field!r}; got: {[(e.attribute, e.errmsg) for e in verrors.errors]}"
    assert fragment in matching[0].errmsg, f"Expected {fragment!r} in error message, got: {matching[0].errmsg!r}"


@pytest.mark.parametrize(
    "flag_override",
    [
        {"bootloader": "UEFI_CSM"},
        {"hyperv_enlightenments": True},
        {"hide_from_msr": True},
    ],
)
@pytest.mark.asyncio
async def test_x86_guest_accepts_x86_flags(flag_override):
    """x86-only flags must not trigger the aarch64 guard on x86 guests."""
    vm_svc = _make_svc()
    data = VMCreate(
        **{
            **_AARCH64_BASE,
            "arch_type": None,
            "bootloader_ovmf": "OVMF_CODE.fd",
            "cpu_mode": "HOST-PASSTHROUGH",
            "cpu_model": None,
            **flag_override,
        }
    )

    with (
        patch("middlewared.plugins.vm.crud.vm_flags", return_value=_VM_FLAGS),
        patch("middlewared.plugins.vm.crud.platform.machine", return_value="x86_64"),
    ):
        verrors = ValidationErrors()
        await vm_svc._svc_part.validate(verrors, "vm_create", data)

    guarded_fields = {"vm_create.bootloader", "vm_create.hyperv_enlightenments", "vm_create.hide_from_msr"}
    spurious = [e for e in verrors.errors if e.attribute in guarded_fields]
    assert not spurious, f"Unexpected aarch64-guard error on x86 guest: {spurious}"


@pytest.mark.parametrize(
    "host_arch,guest_arch,cpu_mode,should_error",
    [
        ("x86_64", "x86_64", "HOST-PASSTHROUGH", False),  # same arch
        ("x86_64", "x86_64", "HOST-MODEL", False),  # same arch, HOST-MODEL
        ("x86_64", "i686", "HOST-PASSTHROUGH", False),  # i686-on-x86_64 family exception
        ("x86_64", "i386", "HOST-PASSTHROUGH", False),  # i386-on-x86_64 family exception
        ("x86_64", "aarch64", "HOST-PASSTHROUGH", True),  # cross-arch: aarch64 guest on x86 host
        ("x86_64", "aarch64", "HOST-MODEL", True),  # cross-arch: HOST-MODEL also rejected
        ("aarch64", "aarch64", "HOST-PASSTHROUGH", False),  # same arch on arm64 host
        ("aarch64", "x86_64", "HOST-PASSTHROUGH", True),  # cross-arch: x86 guest on arm64 host
        ("x86_64", None, "HOST-PASSTHROUGH", False),  # no guest arch → defaults to host
    ],
)
@pytest.mark.asyncio
async def test_cross_arch_cpu_mode(host_arch, guest_arch, cpu_mode, should_error):
    vm_svc = _make_svc()
    data = VMCreate(
        **{
            **_AARCH64_BASE,
            "arch_type": guest_arch,
            "cpu_mode": cpu_mode,
            "cpu_model": None,
            "bootloader_ovmf": "OVMF_CODE.fd",
        }
    )

    with (
        patch("middlewared.plugins.vm.crud.vm_flags", return_value=_VM_FLAGS),
        patch("middlewared.plugins.vm.crud.platform.machine", return_value=host_arch),
        patch("middlewared.plugins.vm.crud.guest_architecture_and_machine_choices", return_value=_ARCH_CHOICES),
    ):
        verrors = ValidationErrors()
        await vm_svc._svc_part.validate(verrors, "vm_create", data)

    cpu_errors = [e for e in verrors.errors if e.attribute == "vm_create.cpu_mode"]
    if should_error:
        assert cpu_errors, (
            f"Expected cpu_mode error for {cpu_mode!r} (guest={guest_arch!r}, host={host_arch!r}); no error raised"
        )
        assert "requires the guest architecture" in cpu_errors[0].errmsg
    else:
        assert not cpu_errors, (
            f"Unexpected cpu_mode error for {cpu_mode!r} "
            f"(guest={guest_arch!r}, host={host_arch!r}): {[e.errmsg for e in cpu_errors]}"
        )
