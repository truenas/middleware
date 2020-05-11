from middlewared.utils import run


async def render(service, middleware):
    advanced = await middleware.call("system.advanced.config")

    config = [
        'GRUB_DISTRIBUTOR="TrueNAS Scale"',
        'GRUB_CMDLINE_LINUX_DEFAULT=""',
    ]

    terminal = ["console"]
    cmdline = []
    if advanced["serialconsole"]:
        config.append(f'GRUB_SERIAL_COMMAND="serial --speed={advanced["serialspeed"]} --word=8 --parity=no --stop=1"')
        terminal.append("serial")

        cmdline.append(f"console={advanced['serialport']},{advanced['serialspeed']} console=tty1")

    config.append(f'GRUB_TERMINAL="{" ".join(terminal)}"')
    config.append(f'GRUB_CMDLINE_LINUX="{" ".join(cmdline)}"')
    config.append("")

    with open("/etc/default/grub.d/truenas.cfg", 'w') as f:
        f.write("\n".join(config))

    await run(["update-grub"], encoding="utf-8", errors="ignore")
