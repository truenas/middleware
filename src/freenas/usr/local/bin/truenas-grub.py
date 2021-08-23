#!/usr/bin/env python3
import sqlite3

from middlewared.plugins.config import FREENAS_DATABASE
from middlewared.utils import osc


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def get_serial_ports():
    return {e['start']: e['name'].replace('uart', 'ttyS') for e in osc.system.serial_port_choices()}


if __name__ == "__main__":
    conn = sqlite3.connect(FREENAS_DATABASE)
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute("SELECT * FROM system_advanced")
    advanced = {k.replace("adv_", ""): v for k, v in c.fetchone().items()}

    config = [
        'GRUB_DISTRIBUTOR="TrueNAS Scale"',
        'GRUB_CMDLINE_LINUX_DEFAULT=""',
    ]

    terminal = ["console"]
    cmdline = []
    if advanced["serialconsole"]:
        config.append(f'GRUB_SERIAL_COMMAND="serial --speed={advanced["serialspeed"]} --word=8 --parity=no --stop=1"')
        terminal.append("serial")

        port = get_serial_ports().get(advanced['serialport'], advanced['serialport'])
        cmdline.append(f"console={port},{advanced['serialspeed']} console=tty1")

    config.append(f'GRUB_TERMINAL="{" ".join(terminal)}"')
    config.append(f'GRUB_CMDLINE_LINUX="{" ".join(cmdline)}"')
    config.append("")

    if osc.IS_FREEBSD:
        path = "/usr/local/etc/default/grub"
    else:
        path = "/etc/default/grub.d/truenas.cfg"

    with open(path, "w") as f:
        f.write("\n".join(config))
