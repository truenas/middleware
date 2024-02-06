import contextlib

from .client import ContainerdClient


def check_containerd_connection() -> bool:
    # Just to clarify that this does not make any internet requests but rather just checks if the socket is available
    # and if we can connect to it. The image check returns nothing if the image is not present.
    with contextlib.suppress(Exception):
        with ContainerdClient('image') as client:
            client.get_image('alpine')
            return True
    return False
