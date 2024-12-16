import contextlib
from time import sleep

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call, ssh

MB = 1024 * 1024


@contextlib.contextmanager
def zvol(name, volsizeMB=512, pool=None, recursive=False, force=False, wait_zvol=True):
    payload = {
        'name': f'{pool}/{name}' if pool else name,
        'type': 'VOLUME',
        'volsize': volsizeMB * MB,
        'volblocksize': '16K'
    }
    config = call('pool.dataset.create', payload)
    try:
        if wait_zvol:
            # Ensure that the zvol has surfaced
            testpath = f'/dev/zvol/{config["name"]}'
            retries = 5
            found = False
            while retries:
                result = ssh(f'ls -1 {testpath}', False, True)
                if result['stdout']:
                    for line in result['stdout'].splitlines():
                        if line == testpath:
                            found = True
                            break
                if found:
                    break
                sleep(1)
                retries -= 1
        yield config
    finally:
        try:
            call('pool.dataset.delete', config['id'], {'recursive': recursive, 'force': force})
        except InstanceNotFound:
            pass
