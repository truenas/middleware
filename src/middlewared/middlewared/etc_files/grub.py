import subprocess

from middlewared.utils import run


async def render(service, middleware):
    try:
        await run(["truenas-grub.py"], encoding="utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        middleware.logger.error("truenas-grub.py error:\n%s", e.stderr)
        raise

    try:
        await run(["update-grub"], encoding="utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        middleware.logger.error("update-grub.py error:\n%s", e.stderr)
        raise
