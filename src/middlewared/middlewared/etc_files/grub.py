import re
import subprocess

DEFAULT_GRUB = '/etc/default/grub'
RE_CMDLINE_LINUX = re.compile(r'^(GRUB_CMDLINE_LINUX=).*"', flags=re.M)
RE_DISTRIBUTOR = re.compile(r'^(GRUB_DISTRIBUTOR=).*', flags=re.M)
RE_SERIAL = re.compile(r'^(GRUB_SERIAL_COMMAND=).*', flags=re.M)
RE_TERMINAL = re.compile(r'^(GRUB_TERMINAL=).*', flags=re.M)


def render(service, middleware):

    with open(DEFAULT_GRUB, 'r') as f:
        default_grub = f.read()

    default_grub = RE_DISTRIBUTOR.sub(r'\1"TrueNAS Scale"', default_grub)

    # Serial port
    advanced = middleware.call_sync('system.advanced.config')
    default_grub = RE_TERMINAL.sub('', default_grub)
    default_grub += 'GRUB_TERMINAL="console{}"'.format(
        ' serial' if advanced['serialconsole'] else '',
    )

    default_grub = RE_SERIAL.sub('', default_grub)
    if advanced['serialconsole']:
        default_grub += (
            '\nGRUB_SERIAL_COMMAND="serial --speed={} --word=8 --parity=no --stop=1"\n'.format(
                advanced['serialspeed'],
            )
        )

    cp = subprocess.run('mount|grep " on / "', capture_output=True, text=True, shell=True)
    if cp.returncode == 0:
        root = cp.stdout.split()[0]
        default_grub = RE_CMDLINE_LINUX.sub(
            r'\1"root={}{}"'.format(
                root,
                f' console={advanced["serialport"]},{advanced["serialspeed"]} console=tty1'
                if advanced['serialconsole'] else '',
            ),
            default_grub,
        )
    else:
        middleware.logger.warn('Failed to determine root filesystem')

    with open(DEFAULT_GRUB, 'w') as f:
        f.write(default_grub)

    cp = subprocess.run(['update-grub'], capture_output=True, text=True)
    if cp.returncode != 0:
        middleware.logger.warn('Failed to update grub: %s', cp.stderr)
