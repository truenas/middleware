from __future__ import annotations

import contextlib
import os
import shutil
import subprocess

from middlewared.service import ServiceContext
from middlewared.utils.mount import umount

from .utils import UPLOAD_LOCATION
from .utils_linux import run_kw


def get_upload_location(context: ServiceContext) -> str:
    return UPLOAD_LOCATION


def create_upload_location(context: ServiceContext) -> str:
    os.makedirs(UPLOAD_LOCATION, exist_ok=True)
    if not os.path.ismount(UPLOAD_LOCATION):
        subprocess.run(
            ["mount", "-o", "size=2800M", "-t", "tmpfs", "none", UPLOAD_LOCATION], **run_kw,
        )  # type: ignore

    for item in os.listdir(UPLOAD_LOCATION):
        item = os.path.join(UPLOAD_LOCATION, item)
        with contextlib.suppress(Exception):
            if os.path.isdir(item):
                shutil.rmtree(item, ignore_errors=True)
            else:
                os.unlink(item)

    shutil.chown(UPLOAD_LOCATION, "www-data", "www-data")
    os.chmod(UPLOAD_LOCATION, 0o755)
    return UPLOAD_LOCATION


def destroy_upload_location(context: ServiceContext) -> None:
    if os.path.ismount(UPLOAD_LOCATION):
        umount(UPLOAD_LOCATION)
