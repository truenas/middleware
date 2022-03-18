#!/usr/bin/env python3
import math
import psutil

from middlewared.utils.serial_devices import serial_port_choices
from middlewared.utils.db import query_config_table


def get_serial_ports():
    return {e['start']: e['name'].replace('uart', 'ttyS') for e in serial_port_choices()}


if __name__ == "__main__":
    advanced = query_config_table("system_advanced", prefix="adv_")
    kernel_extra_args = advanced.get('kernel_extra_options') or ''

    # We need to allow tpm in grub as sedutil-cli requires it
    # `zfsforce=1` is needed because FreeBSD bootloader imports boot pool with hostid=0 while SCALE releases up to
    # 22.02-RC.2 use real hostid. We need to be able to boot both of these configurations.
    # TODO: Please remove kernel flag to use cgroups v1 when nvidia device plugin starts working
    #  with it ( https://github.com/NVIDIA/k8s-device-plugin/issues/235 )
    config = [
        'GRUB_DISTRIBUTOR="TrueNAS Scale"',
        'GRUB_CMDLINE_LINUX_DEFAULT="libata.allow_tpm=1 systemd.unified_cgroup_hierarchy=0 amd_iommu=on iommu=pt '
        'kvm_amd.npt=1 kvm_amd.avic=1 intel_iommu=on zfsforce=1'
        f'{f" {kernel_extra_args}" if kernel_extra_args else ""}"',
    ]

    terminal = ["console"]
    cmdline = []
    if advanced["serialconsole"]:
        config.append(f'GRUB_SERIAL_COMMAND="serial --speed={advanced["serialspeed"]} --word=8 --parity=no --stop=1"')
        terminal.append("serial")
        port = get_serial_ports().get(advanced['serialport'], advanced['serialport'])
        cmdline.append(f"console={port},{advanced['serialspeed']} console=tty1")

    if advanced.get("kdump_enabled"):
        # (memory in kb) / 16 / 1024 / 1024
        # For every 4KB of physical memory, we should allocate 2 bits to the crash kernel
        # In other words, for every 16KB of memory we allocate 1 byte.
        # https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/7/html/
        # kernel_administration_guide/kernel_crash_dump_guide#sect-kdump-memory-requirements
        #
        # We should test this on systems with higher memory as there are contradicting
        # docs - https://www.suse.com/support/kb/doc/?id=000016171
        # With our custom kernel, having 256MB RAM as base is not enough.
        # In my tests it worked with having 400MB as base RAM.
        # TODO: Let's please see what we can do to bring this down on the kernel side perhaps
        current_mem = psutil.virtual_memory().total / 1024
        cmdline.append(f"crashkernel={400 + math.ceil(current_mem / 16 / 1024 / 1024)}M")

    config.append(f'GRUB_TERMINAL="{" ".join(terminal)}"')
    config.append(f'GRUB_CMDLINE_LINUX="{" ".join(cmdline)}"')
    config.append("")

    with open("/etc/default/grub.d/truenas.cfg",  "w") as f:
        f.write("\n".join(config))
