# -*- coding=utf-8 -*-
import contextlib
import logging
import subprocess
import tempfile

from middlewared.service import CallError

logger = logging.getLogger(__name__)

run_kw = dict(check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="ignore")


@contextlib.contextmanager
def mount_update(path):
    with tempfile.TemporaryDirectory() as mounted:
        try:
            subprocess.run(["mount", "-t", "squashfs", "-o", "loop", path, mounted], **run_kw)
        except subprocess.CalledProcessError as e:
            raise CallError(f"Invalid update image file. Please, re-download update. Error: {e.stdout}")
        try:
            yield mounted
        finally:
            subprocess.run(["umount", mounted], **run_kw)
