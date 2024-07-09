import json
import time

from middlewared.test.integration.utils import call, ssh

"""
We use 'parted' to partition disks.
Verification is based on 'parted' documentation (https://people.redhat.com/msnitzer/docs/io-limits.txt):
    The heuristic parted uses is:
    1)  Always use the reported 'alignment_offset' as the offset for the
        start of the first primary partition.
    2a) If 'optimal_io_size' is defined (not 0) align all partitions on an
        'optimal_io_size' boundary.
    2b) If 'optimal_io_size' is undefined (0) and 'alignment_offset' is 0
        and 'minimum_io_size' is a power of 2: use a 1MB default alignment.
        - as you can see this is the catch all for "legacy" devices which
          don't appear to provide "I/O hints"; so in the default case all
          partitions will align on a 1MB boundary.
        - NOTE: we can't distinguish between a "legacy" device and modern
          device that provides "I/O hints" with alignment_offset=0 and
          optimal_io_size=0.  Such a device might be a single SAS 4K device.
          So worst case we lose < 1MB of space at the start of the disk.
"""
# Some 'constants'
MBR_SECTOR_GAP = 34
ONE_MB = 1048576
DATA_TYPE_UUID = "6a898cc3-1dd2-11b2-99a6-080020736631"


def get_parted_info(disk_path):
    # By the time this is called, the disk has been formatted
    # but the kernel might not have been made fully aware of the changes
    # so let's retry a bit before failing
    for i in range(10):
        pbytes = json.loads(ssh(f'parted {disk_path} unit b p --json'))['disk']
        if pbytes.get('partitions') is None:
            time.sleep(1)
        else:
            break
    else:
        assert False, f'parted tool failed to find partitions (in bytes) on {disk_path!r} ({pbytes!r})'

    for i in range(10):
        psectors = json.loads(ssh(f'parted {disk_path} unit s p --json'))['disk']
        if psectors.get('partitions') is None:
            time.sleep(1)
        else:
            break
    else:
        assert False, f'parted tool failed to find partitions (in sectors) on {disk_path!r} ({psectors!r})'

    return pbytes, psectors


def test_disk_format_and_wipe():
    """Generate a single data partition"""
    # get an unused disk and format it
    unused = call('disk.get_unused')
    assert unused, 'Need at least 1 unused disk'
    call('disk.format', unused[0]['name'])
    partitions = call('disk.list_partitions', unused[0]['name'])
    assert partitions, partitions

    # The first and only partition should be data
    assert len(partitions) == 1, partitions
    partition = partitions[0]
    assert partition['partition_type'] == DATA_TYPE_UUID

    # we used libparted to format a drive so let's
    # validate our API matches parted output (NOTE:
    # we check both bytes and sectors)
    parted_bytes, parted_sectors = get_parted_info(f'/dev/{unused[0]["name"]}')

    # sanity check (make sure parted shows same number of partitions)
    assert len(parted_bytes['partitions']) == len(partitions), parted_bytes['partitions']
    assert len(parted_sectors['partitions']) == len(partitions), parted_sectors['partitions']

    # validate our API shows proper start/end sizes in bytes
    pbyte = parted_bytes['partitions'][0]
    assert int(pbyte['size'].split('B')[0]) == partition['size']
    assert int(pbyte['start'].split('B')[0]) == partition['start']
    assert int(pbyte['end'].split('B')[0]) == partition['end']

    # validate our API shows proper start/end sizes in sectors
    psect = parted_sectors['partitions'][0]
    assert int(psect['start'].split('s')[0]) == partition['start_sector']
    assert int(psect['end'].split('s')[0]) == partition['end_sector']

    # verify wipe disk should removes partition labels
    call('disk.wipe', partition['disk'], 'QUICK', job=True)
    # the partitions are removed
    new_parts = call('disk.list_partitions', partition['disk'])
    assert len(new_parts) == 0, new_parts

    # sanity check, make sure parted doesn't see partitions either
    pbytes = json.loads(ssh(f'parted /dev/{unused[0]["name"]} unit b p --json'))['disk']
    assert pbytes.get('partitions') is None, repr(pbytes)
