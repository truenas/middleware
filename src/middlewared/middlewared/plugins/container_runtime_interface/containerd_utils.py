import contextlib

from .client import ContainerdClient


def check_containerd_connection() -> bool:
    with contextlib.suppress(Exception):
        with ContainerdClient('image') as client:
            client.get_image('alpine')
            return True
    return False
