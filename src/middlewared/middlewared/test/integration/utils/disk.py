import time

from middlewared.test.integration.utils import call

__all__ = ['retry_get_parts_on_disk']


def retry_get_parts_on_disk(disk, max_tries=10):
    for i in range(max_tries):
        if parts := call('disk.list_partitions', disk):
            return parts
        time.sleep(1)
    else:
        assert False, f'Failed after {max_tries} seconds for partition info on {disk!r}'
