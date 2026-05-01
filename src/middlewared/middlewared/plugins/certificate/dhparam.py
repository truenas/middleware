import os
import subprocess

DHPARAM_PEM_PATH: str = '/data/dhparam.pem'


def dhparam_setup() -> None:
    with open(DHPARAM_PEM_PATH, 'a+') as f:
        if os.fstat(f.fileno()).st_size == 0:
            subprocess.run(
                ['openssl', 'dhparam', '-out', DHPARAM_PEM_PATH, '-rand', '/dev/urandom', '2048'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
            )
            os.fchmod(f.fileno(), 0o600)
