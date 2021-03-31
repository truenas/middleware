#!/usr/bin/env python3
import math
import psutil

from middlewared.utils import osc
from middlewared.utils.db import query_config_table


if __name__ == "__main__":
    advanced = query_config_table("system_advanced", prefix="adv_")

    # We need to allow tpm in grub as sedutil-cli requires it
    # TODO: Please remove kernel flag to use cgroups v1 when nvidia device plugin starts working
    #  with it ( https://github.com/NVIDIA/k8s-device-plugin/issues/235 )
    config = [
        'GRUB_DISTRIBUTOR="TrueNAS Scale"',
        'GRUB_CMDLINE_LINUX_DEFAULT="libata.allow_tpm=1 systemd.unified_cgroup_hierarchy=0 '
        'amd_iommu=on iommu=pt kvm_amd.npt=1 kvm_amd.avic=1 intel_iommu=on"',
    ]

    terminal = ["console"]
    cmdline = []
    if advanced["serialconsole"]:
        config.append(f'GRUB_SERIAL_COMMAND="serial --speed={advanced["serialspeed"]} --word=8 --parity=no --stop=1"')
        terminal.append("serial")

        cmdline.append(f"console={advanced['serialport']},{advanced['serialspeed']} console=tty1")

    if advanced.get("kdump_enabled"):
        # (memory in kb) / 16 / 1024 / 1024
        # For every 4KB of physical memory, we should allocate 2 bits to the crash kernel
        # In other words, for every 16KB of memory we allocate 1 byte.
        # https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/7/html/
        # kernel_administration_guide/kernel_crash_dump_guide#sect-kdump-memory-requirements
        #
        # We should test this on systems with higher memory as there are contradicting
        # docs - https://www.suse.com/support/kb/doc/?id=000016171
        current_mem = psutil.virtual_memory().total / 1024
        cmdline.append(f"crashkernel={256 + math.ceil(current_mem / 16 / 1024 / 1024)}M")

    config.append(f'GRUB_TERMINAL="{" ".join(terminal)}"')
    config.append(f'GRUB_CMDLINE_LINUX="{" ".join(cmdline)}"')
    config.append("")

    if osc.IS_FREEBSD:
        path = "/usr/local/etc/default/grub"
    else:
        path = "/etc/default/grub.d/truenas.cfg"

    with open(path, "w") as f:
        f.write("\n".join(config))
