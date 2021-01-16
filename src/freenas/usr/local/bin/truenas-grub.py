#!/usr/bin/env python3
import math
import psutil
import sqlite3

from middlewared.plugins.config import FREENAS_DATABASE
from middlewared.utils import osc


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


if __name__ == "__main__":
    conn = sqlite3.connect(FREENAS_DATABASE)
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute("SELECT * FROM system_advanced")
    advanced = {k.replace("adv_", ""): v for k, v in c.fetchone().items()}

    # We need to allow tpm in grub as sedutil-cli requires it
    # TODO: Please remove kernel flag to use cgroups v1 when upstream k3s has support for cgroups v2
    config = [
        'GRUB_DISTRIBUTOR="TrueNAS Scale"',
        'GRUB_CMDLINE_LINUX_DEFAULT="libata.allow_tpm=1 systemd.unified_cgroup_hierarchy=0"',
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
