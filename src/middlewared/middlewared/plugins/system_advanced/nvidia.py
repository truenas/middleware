from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

from truenas_pylibvirt.utils.gpu import get_gpus

from middlewared.utils.rootfs_protection import rootfs_protection_lock

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


def nvidia_present(context: ServiceContext) -> bool:
    adv_config = context.call_sync2(context.s.system.advanced.config)
    for gpu in get_gpus():
        if gpu['addr']['pci_slot'] in adv_config.isolated_gpu_pci_ids:
            continue
        if gpu['vendor'] == 'NVIDIA':
            return True
    return False


async def handle_nvidia_toggle(context: ServiceContext) -> None:
    # this only gets called if nvidia setting was toggled
    # which means we need to restart apps once we have run our configuration logic
    await context.to_thread(configure_nvidia, context)
    if (await context.middleware.call('docker.config')).pool:
        # We explicitly have it non-blocking here as docker restart on HDD based systems can take
        # decent amount of time
        context.create_task(context.middleware.call('docker.restart_service'))


def configure_nvidia(context: ServiceContext) -> None:
    config = context.call_sync2(context.s.system.advanced.config)
    nvidia_sysext_path = '/run/extensions/nvidia.raw'
    if config.nvidia and not os.path.exists(nvidia_sysext_path):
        os.makedirs('/run/extensions', exist_ok=True)
        os.symlink('/usr/share/truenas/sysext-extensions/nvidia.raw', nvidia_sysext_path)
        refresh = True
    elif not config.nvidia and os.path.exists(nvidia_sysext_path):
        os.unlink(nvidia_sysext_path)
        refresh = True
    else:
        refresh = False

    if refresh:
        # systemd-sysext refresh re-overlays /usr; hold the rootfs lock so it
        # can't race the initramfs rebuild or disable-rootfs-protection.
        with rootfs_protection_lock():
            subprocess.run(['systemd-sysext', 'refresh'], capture_output=True, check=True, text=True)
            subprocess.run(['ldconfig'], capture_output=True, check=True, text=True)

    if config.nvidia:
        cp = subprocess.run(
            ['modprobe', '-a', 'nvidia', 'nvidia_drm', 'nvidia_modeset'],
            capture_output=True,
            text=True
        )
        if cp.returncode != 0:
            context.logger.error('Error loading nvidia driver: %s', cp.stderr)
        else:
            # Needed to verify that NVIDIA character devices are present and functioning correctly.
            smi_cp = subprocess.run(
                ['nvidia-smi'],
                capture_output=True,
            )
            if smi_cp.returncode != 0:
                context.logger.error('Error while setting up nvidia gpu: %s', smi_cp.stderr)
