import logging
import subprocess
import sysctl
import os
from packaging import version

from middlewared.utils.io import write_if_changed

logger = logging.getLogger(__name__)


def loader_config(middleware):
    config = generate_loader_config(middleware)
    path = "/boot/loader.conf.local"
    write_if_changed(path, "\n".join(config) + "\n")

    # write_if_changed creates the file with
    # the execute bit so remove it
    try:
        os.chmod(path, 0o644)
    except Exception:
        # dont crash here
        pass


def generate_loader_config(middleware):
    generators = [
        generate_serial_loader_config,
        generate_user_loader_config,
        generate_debugkernel_loader_config,
        generate_ha_loader_config,
        generate_ec2_config,
        generate_truenas_logo,
        generate_dual_nvdimm_config,
    ]
    if not middleware.call_sync("system.is_enterprise"):
        generators.append(generate_xen_loader_config)

    config = []
    for generator in generators:
        try:
            config.extend(generator(middleware) or [])
        except Exception as e:
            middleware.logger.error("Failed to load generator: %r with error: %s", generator, e)
            continue

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
    mseries = middleware.call_sync("failover.hardware") == "ECHOWARP"

    if advanced["serialconsole"]:
        if sysctl.filter("machdep.bootmethod")[0].value == "UEFI":
            # The efi console driver can do both video and serial output.
            # Don't enable it if it has a serial output, otherwise we may
            # output twice to the same serial port in loader.
            # However, enabling serial output on UEFI booted m-series devices
            # causes the boot loader screen to not show on the iKVM/HTML5 IPMI
            # website.
            consoles = list_efi_consoles()
            if any(path.find('Serial') != -1 for path in consoles) and not mseries:
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
    proc = middleware.call_sync('system.dmidecode_info')['system-product-name']
    if proc == "HVM domU":
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


def generate_dual_nvdimm_config(middleware):
    data = middleware.call_sync('system.dmidecode_info')

    product = data['system-product-name']

    # 0123456789/12345679 are some of the default values
    # that we've seen from supermicro.
    # Before the version 3 hardware, we were not changing
    # this value so this is a way to identify version 1/2
    # m-series hardware.
    if data['system-version'] in ('0123456789', '123456789'):
        return

    try:
        current_vers = version.parse(data['system-version'])
        minimum_vers = version.Version('3.0')
    except Exception as e:
        middleware.logger.error('Failed determining hardware version with error: %s', e)
        return

    # for now we only check to make sure that the current version is 3 because
    # we quickly found out that the SMBIOS defaults for the system-version value
    # from supermicro aren't very predictable. Since setting these values on a
    # system that doesn't support the dual-nvdimm configs leads to "no carrier"
    # on the ntb0 interface, we play it safe. The `minimum_vers` will need to be
    # changed as time goes on if we start tagging hardware with 4.0,5.0 etc etc
    if product.startswith('TRUENAS-M') and current_vers.major == minimum_vers.major:
        return [
            'hint.ntb_hw.0.split=1',
            'hint.ntb_hw.0.config="ntb_pmem:1:4:0,ntb_pmem:1:4:0,ntb_transport"'
        ]


def render(service, middleware):
    loader_config(middleware)
