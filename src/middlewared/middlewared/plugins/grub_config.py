"""
Single source of truth for `/etc/default/grub.d/truenas.cfg`.

The bytes are rendered from `system.advanced` + vendor + hardware + memory on
the live system and written to two locations:

  - `/etc/default/grub.d/truenas.cfg` - consumed by `grub-mkconfig` on the
    running BE.
  - `/data/subsystems/grub/truenas.cfg` - persisted snapshot. The installer
    rsyncs `/data` into the newly-extracted BE during an upgrade, and the
    stdlib-only `upgrade_pyutils` `truenas-grub.py` script reads the snapshot
    from the new BE's `/data` and lays it down at the new BE's
    `/etc/default/grub.d/truenas.cfg` before `update-grub` runs.

This snapshot pattern exists because the old `truenas-grub.py` imported from
`middlewared` and ran under the new BE's Python during upgrade, which is the
same cross-version path that bricked upgrades for `truenas-initrd.py`. See
upgrade_pyutils/README.md for the full motivation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import math
import os
import typing

from truenas_os_pyutils.io import atomic_write

from middlewared.utils.memory import get_memory_info
from middlewared.utils.serial import serial_port_choices
from middlewared.utils.vendor import Vendors

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


GRUB_CFG_PATH = "/etc/default/grub.d/truenas.cfg"
GRUB_CFG_DATA_PATH = "/data/subsystems/grub/truenas.cfg"
VENDOR_FILE = "/data/.vendor"


@dataclass(frozen=True, slots=True)
class KernelParam:
    """One entry in the default kernel command line. `reason` is mandatory
    so every param's rationale lives next to it and survives the original
    author leaving."""

    arg: str
    reason: str

    def __post_init__(self) -> None:
        if len(self.reason.strip()) < 30:
            raise ValueError(
                f"{self.arg!r}: reason must be a real sentence explaining why "
                f"this param is on the cmdline, not {self.reason!r}"
            )


# Order is preserved on the rendered cmdline. Append new entries; don't
# reorder existing ones without checking it doesn't affect parsing of any
# kvm_* / kernel.* group.
KERNEL_PARAMS: tuple[KernelParam, ...] = (
    KernelParam(
        "libata.allow_tpm=1",
        "libata blocks the ATA Trusted Send / Trusted Receive commands by "
        "default, which breaks SED (TCG OPAL) management on SATA drives. "
        "NVMe SEDs don't go through libata so they don't need this.",
    ),
    KernelParam(
        "amd_iommu=on",
        "Required for PCI passthrough on AMD platforms (LXC container GPU passthrough, SR-IOV networking).",
    ),
    KernelParam(
        "iommu=pt",
        "Passthrough mode: IOMMU translates only for devices assigned to a "
        "guest, not for all host DMA. Avoids the perf hit on host I/O "
        "while still enabling passthrough.",
    ),
    KernelParam(
        "kvm_amd.npt=1",
        "Enable Nested Page Tables on AMD; major perf win for VM memory "
        "translation. Default in modern kernels but pinned to guard "
        "against regressions.",
    ),
    KernelParam(
        "kvm_amd.avic=1",
        "Enable Advanced Virtual Interrupt Controller on AMD; bypasses VMEXIT for most interrupt delivery to guests.",
    ),
    KernelParam(
        "intel_iommu=on",
        "Required for PCI passthrough on Intel platforms. Counterpart to "
        "amd_iommu=on; only one applies per boot but we set both because "
        "the same image runs on both vendors.",
    ),
    KernelParam(
        "zfsforce=1",
        "FreeBSD bootloader imports the boot pool with hostid=0, but SCALE "
        "releases up to 22.02-RC.2 wrote a real hostid. We need to boot "
        "both layouts after an upgrade, so force the import.",
    ),
    KernelParam(
        "nvme_core.multipath=N",
        "Multipath-capable NVMe devices otherwise expose actual block "
        "devices as nvme0c0n1 to udev while the nvme0n1 nodes appear as "
        "virtual block devices, with no straightforward mapping between "
        "the two. We don't use NVMe multipath; disable it for consistent "
        "block enumeration across multipath-capable and non-multipath-"
        "capable hardware.",
    ),
)

KERNEL_CMDLINE_DEFAULT = " ".join(p.arg for p in KERNEL_PARAMS)


def _read_vendor() -> str:
    try:
        with open(VENDOR_FILE) as f:
            return json.load(f).get("name") or Vendors.TRUENAS_SCALE
    except FileNotFoundError:
        return Vendors.TRUENAS_SCALE


def render_grub_config(middleware: Middleware) -> str:
    """Compute the `truenas.cfg` content. Pure function of DB + hardware +
    memory; no side effects."""
    advanced = middleware.call_sync2(middleware.services.system.advanced.config)
    vendor = _read_vendor()
    kernel_extra_options = advanced.kernel_extra_options or ""

    cmdline_default = KERNEL_CMDLINE_DEFAULT
    if kernel_extra_options:
        cmdline_default = f"{cmdline_default} {kernel_extra_options}"
    config = [
        f'GRUB_DISTRIBUTOR="{vendor}"',
        "GRUB_TIMEOUT=10",
        'GRUB_DISABLE_RECOVERY="true"',
        f'GRUB_CMDLINE_LINUX_DEFAULT="{cmdline_default}"',
    ]

    terminal_output = ["console"]
    terminal_input = ["console"]
    cmdline: list[str] = []
    if advanced.serialconsole:
        ports = {e["start"]: e["name"].replace("uart", "ttyS") for e in serial_port_choices()}
        port = ports.get(advanced.serialport, advanced.serialport)
        port_nr = port.replace("ttyS", "")
        config.append(
            f'GRUB_SERIAL_COMMAND="serial --unit={port_nr}'
            f' --speed={advanced.serialspeed} --word=8 --parity=no --stop=1"'
        )
        if os.path.exists("/sys/firmware/efi"):
            terminal_output = ["gfxterm"]
        terminal_output.append("serial")
        terminal_input.append("serial")
        cmdline.append(f"console=tty1 console={port},{advanced.serialspeed}")

    if advanced.kdump_enabled:
        # For every 4KB of physical memory allocate 2 bits to the crash
        # kernel (1 byte per 16KB). 400MB base was needed in testing for our
        # custom kernel; see RHEL kdump memory requirements and the
        # contradicting SUSE doc id 000016171.
        current_mem = get_memory_info()["total"] / 1024
        cmdline.append(f"crashkernel={400 + math.ceil(current_mem / 16 / 1024 / 1024)}M")

    config.append(f'GRUB_TERMINAL_INPUT="{" ".join(terminal_input)}"')
    config.append(f'GRUB_TERMINAL_OUTPUT="{" ".join(terminal_output)}"')
    config.append(f'GRUB_CMDLINE_LINUX="{" ".join(cmdline)}"')
    config.append("")
    return "\n".join(config)


def _atomic_replace_if_changed(path: str, content: str, tmppath: str | None = None) -> bool:
    try:
        with open(path) as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""
    if existing == content:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with atomic_write(path, "w", tmppath=tmppath) as f:
        f.write(content)
    return True


def write_grub_config(middleware: Middleware) -> bool:
    """Render the config and write both the running-BE file and the persisted
    snapshot under `/data`. Returns True if either file changed.

    On HA, each node renders from its own (replicated) DB rather than shipping
    bytes across — same pattern as hostname/hosts/sysctl/fips. Propagation to
    the remote node is the caller's responsibility (via
    `failover.call_remote 'etc.generate' ['grub']`), not this function's.

    Sync - call from a thread (`asyncio.to_thread`) when invoked from a
    coroutine."""
    content = render_grub_config(middleware)

    # The running-BE file is written to /etc/default rather than directly into
    # /etc/default/grub.d to avoid any chance of an unintended file landing in
    # the grub.d directory (matches the old script's behavior).
    changed = _atomic_replace_if_changed(GRUB_CFG_PATH, content, tmppath="/etc/default")
    snapshot_changed = _atomic_replace_if_changed(GRUB_CFG_DATA_PATH, content)
    return changed or snapshot_changed


async def _event_system_ready(middleware, event_type, args):
    # Don't block boot
    middleware.create_task(_reconcile(middleware))


async def _reconcile(middleware):
    try:
        changed = await asyncio.to_thread(write_grub_config, middleware)
        if changed:
            # write_grub_config only updates /etc/default/grub.d/truenas.cfg
            # (the input). etc.generate('grub') runs grub-mkconfig to compile
            # that into /boot/grub/grub.cfg, which is what the bootloader
            # actually reads. Without this the next boot uses stale params.
            await middleware.call("etc.generate", "grub")
        if await middleware.call("failover.licensed"):
            if await middleware.call("failover.status") != "MASTER":
                return
            try:
                await middleware.call("failover.call_remote", "etc.generate", ["grub"])
            except Exception:
                middleware.logger.error(
                    "failed to render grub.cfg on remote node", exc_info=True
                )
    except Exception:
        middleware.logger.error("Failed to reconcile grub config", exc_info=True)


async def setup(middleware):
    middleware.event_subscribe("system.ready", _event_system_ready)
