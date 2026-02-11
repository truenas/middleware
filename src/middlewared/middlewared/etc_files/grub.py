import os
import subprocess

from middlewared.utils import run

GRUB_CFG = '/boot/grub/grub.cfg'
GRUB_CFG_TMP = '/boot/grub/grub.cfg.tmp'


async def render(service, middleware):
    try:
        await run(["truenas-grub.py"], encoding="utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        middleware.logger.error("truenas-grub.py error:\n%s", e.stderr)
        raise

    try:
        await run(["grub-mkconfig", "-o", GRUB_CFG_TMP], encoding="utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        middleware.logger.error("grub-mkconfig error:\n%s", e.stderr)
        raise

    with open(GRUB_CFG_TMP, 'r') as f:
        os.fsync(f.fileno())

    os.replace(GRUB_CFG_TMP, GRUB_CFG)
