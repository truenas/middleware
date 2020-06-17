import logging
import subprocess
import sysctl

from middlewared.utils.io import write_if_changed

logger = logging.getLogger(__name__)


def loader_config(middleware):
    config = generate_loader_config(middleware)
    write_if_changed("/boot/loader.conf.local", "\n".join(config) + "\n")


def generate_loader_config(middleware):
    generators = [
        generate_serial_loader_config,
        generate_user_loader_config,
        generate_debugkernel_loader_config,
        generate_ha_loader_config,
        generate_ec2_config,
        generate_truenas_logo,
    ]
    if middleware.call_sync("system.is_freenas"):
        generators.append(generate_xen_loader_config)

    config = []
    for generator in generators:
        config.extend(generator(middleware) or [])

    return config


def generate_truenas_logo(middleware):
    return [f'loader_logo="TrueNAS{middleware.call_sync("system.product_type").capitalize()}"']


def list_efi_consoles():
    def efivar(*args):
        cmd = subprocess.run(['efivar', *args], capture_output=True, text=True)
        return cmd.stdout.strip()

    for var in efivar('-l').splitlines():
        if var.endswith('ConOut'):
            return efivar('-Nd', var).split(',/')
    return []


def generate_serial_loader_config(middleware):
    advanced = middleware.call_sync("system.advanced.config")
    if advanced["serialconsole"]:
        if sysctl.filter("machdep.bootmethod")[0].value == "UEFI":
            # The efi console driver can do both video and serial output.
            # Don't enable it if it has a serial output, otherwise we may
            # output twice to the same serial port in loader.
            consoles = list_efi_consoles()
            if any(path.find('Serial') != -1 for path in consoles):
                # Firmware gave efi a serial port.
                # Use only comconsole to avoid duplicating output.
                console = "comconsole"
            else:
                console = "comconsole,efi"
        else:
            console = "comconsole,vidconsole"
        return [
            f'comconsole_port="{advanced["serialport"]}"',
            f'comconsole_speed="{advanced["serialspeed"]}"',
            'boot_multicons="YES"',
            'boot_serial="YES"',
            f'console="{console}"',
        ]

    return []


def generate_user_loader_config(middleware):
    return [
        f'{tunable["var"]}=\"{tunable["value"]}\"' + (f' # {tunable["comment"]}' if tunable["comment"] else '')
        for tunable in middleware.call_sync("tunable.query", [["type", "=", "LOADER"], ["enabled", "=", True]])
    ]


def generate_debugkernel_loader_config(middleware):
    advanced = middleware.call_sync("system.advanced.config")
    if advanced["debugkernel"]:
        return [
            'kernel="kernel-debug"',
        ]
    else:
        return [
            'kernel="kernel"',
        ]


def generate_ha_loader_config(middleware):
    if middleware.call_sync("iscsi.global.alua_enabled"):
        node = middleware.call_sync("failover.node")
        if node == "A":
            return ["kern.cam.ctl.ha_id=1"]
        if node == "B":
            return ["kern.cam.ctl.ha_id=2"]

        return []

    return ["kern.cam.ctl.ha_id=0"]


def generate_xen_loader_config(middleware):
    proc = subprocess.run(["/usr/local/sbin/dmidecode", "-s", "system-product-name"], stdout=subprocess.PIPE)
    if proc.returncode == 0 and proc.stdout.strip() == b"HVM domU":
        return ['hint.hpet.0.clock="0"']

    return []


def generate_ec2_config(middleware):
    if middleware.call_sync("system.environment") == "EC2":
        return [
            'if_ena_load="YES"',
            'autoboot_delay="-1"',
            'beastie_disable="YES"',
            'boot_multicons="YES"',
            'hint.atkbd.0.disabled="1"',
            'hint.atkbdc.0.disabled="1"',
        ]


def render(service, middleware):
    loader_config(middleware)
