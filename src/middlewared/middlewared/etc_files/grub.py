import os
import subprocess

GRUB_CFG = '/boot/grub/grub.cfg'
GRUB_CFG_TMP = '/boot/grub/grub.cfg.tmp'


def render(service, middleware):
    try:
        subprocess.run(["truenas-grub.py"], capture_output=True, check=True, encoding="utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        middleware.logger.error("truenas-grub.py error:\n%s", e.stderr)
        raise

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
