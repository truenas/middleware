# -*- coding=utf-8 -*-
import contextlib
import subprocess
import tempfile

run_kw = dict(check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="ignore")


@contextlib.contextmanager
def mount_update(path):
    with tempfile.TemporaryDirectory() as mounted:
        subprocess.run(["mount", "-t", "squashfs", "-o", "loop", path, mounted], **run_kw)
        try:
            yield mounted
        finally:
            subprocess.run(["umount", mounted], **run_kw)
