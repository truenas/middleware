import logging
import os
import subprocess
import sysctl

logger = logging.getLogger(__name__)

FIRST_INSTALL_SENTINEL = "/data/first-boot"


def loader_config(middleware, allow_reboot=True):
    reboot = autotune(middleware)

    config = generate_loader_config(middleware)

    # Using the ix-loader script to also do post-first-install stuff
    # We should create a seperate ix-firstinstall script
    # if we add more things later.
    if os.path.exists(FIRST_INSTALL_SENTINEL):
        # Delete sentinel file before making clone as we
        # we do not want the clone to have the file in it.
        os.unlink(FIRST_INSTALL_SENTINEL)

        # Creating pristine boot environment from the "default"
        logger.info("Creating 'Initial-Install' boot environment...")
        subprocess.run(["/usr/local/sbin/beadm", "create", "-e", "default", "Initial-Install"])

    with open("/boot/loader.conf.local", "w") as f:
        f.write("\n".join(config) + "\n")

    if allow_reboot:
        if reboot:
            subprocess.run(["shutdown", "-r", "now"])


def autotune(middleware):
    if middleware.call_sync("system.is_freenas"):
        args = ["--kernel-reserved=1073741824", "--userland-reserved=2417483648"]
    else:
        args = ["--kernel-reserved=6442450944", "--userland-reserved=4831838208"]

    p = subprocess.run(["/usr/local/bin/autotune", "-o"] + args)
    if p.returncode == 2:
        # Values changed based on recommendations. Reboot [eventually].
        return True
    else:
        return False


def generate_loader_config(middleware):
    generators = [generate_serial_loader_config, generate_user_loader_config, generate_debugkernel_loader_config,
                  generate_ha_loader_config]
    if middleware.call_sync("system.is_freenas"):
        generators.append(generate_xen_loader_config)

    config = []
    for generator in generators:
        config.extend(generator(middleware))

    return config


def generate_serial_loader_config(middleware):
    advanced = middleware.call_sync("system.advanced.config")
    if advanced["serialconsole"]:
        if sysctl.filter("machdep.bootmethod")[0].value == "UEFI":
            videoconsole = "efi"
        else:
            videoconsole = "vidconsole"

        return [
            f'comconsole_port="{advanced["serialport"]}"',
            f'comconsole_speed="{advanced["serialspeed"]}"',
            'boot_multicons="YES"',
            'boot_serial="YES"',
            f'console="comconsole,{videoconsole}"',
        ]

    return []


def generate_user_loader_config(middleware):
    return [
        f'{tunable["var"]}=\"{tunable["value"]}\"' + (f' # {tunable["comment"]}' if tunable["comment"] else '000')
        for tunable in middleware.call_sync("tunable.query", [["type", "=", "LOADER"]])
    ]


def generate_debugkernel_loader_config(middleware):
    advanced = middleware.call_sync("system.advanced.config")
    if advanced["debugkernel"]:
        return [
            'kernel="kernel-debug"',
            'module_path="/boot/kernel-debug;/boot/modules;/usr/local/modules"',
        ]
    else:
        return [
            'kernel="kernel"',
            'module_path="/boot/kernel;/boot/modules;/usr/local/modules"'
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
    if proc.returncode == 0 and proc.stdout.strip() == "HVM domU":
        return ['hint.hpet.0.clock="0"']

    return []


async def render(service, middleware):
    await middleware.run_in_thread(loader_config, middleware, service.args[0] if service.args else True)
