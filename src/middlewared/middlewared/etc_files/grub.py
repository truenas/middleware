import os
import subprocess

from middlewared.plugins.grub_config import write_grub_config

GRUB_CFG = '/boot/grub/grub.cfg'
GRUB_CFG_TMP = '/boot/grub/grub.cfg.tmp'


def render(service, middleware):
    write_grub_config(middleware)

    try:
        subprocess.run(
            ["grub-mkconfig", "-o", GRUB_CFG_TMP], check=True, capture_output=True, encoding="utf-8", errors="ignore",
        )
    except subprocess.CalledProcessError as e:
        middleware.logger.error("grub-mkconfig error:\n%s", e.stderr)
        raise

    with open(GRUB_CFG_TMP, 'r') as f:
        os.fsync(f.fileno())

    os.replace(GRUB_CFG_TMP, GRUB_CFG)
