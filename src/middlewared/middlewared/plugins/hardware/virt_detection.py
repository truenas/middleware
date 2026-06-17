import functools
import os
import subprocess


@functools.cache
def detect_variant() -> str:
    rv = subprocess.run(["systemd-detect-virt"], capture_output=True)
    return rv.stdout.decode().strip()


def is_virtualized() -> bool:
    return detect_variant() != "none"


@functools.cache
def guest_vms_supported() -> bool:
    return os.path.exists("/dev/kvm")
