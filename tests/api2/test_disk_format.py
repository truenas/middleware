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
    for i in range(5):
        parted_bytes = json.loads(ssh(f'parted {disk_path} unit b p --json'))['disk']
        if parted_bytes.get('partitions') is None:
            time.sleep(1)
        else:
            break
    else:
        assert False, f'parted tool failed to find partitions (in bytes) on {disk_path!r}'

    for i in range(5):
        parted_sectors = json.loads(ssh(f'parted {disk_path} unit s p --json'))['disk']
        if parted_bytes.get('partitions') is None:
            time.sleep(1)
        else:
            break
    else:
        assert False, f'parted tool failed to find partitions (in sectors) on {disk_path!r}'

    return parted_bytes, parted_sectors


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
    pb_byte = parted_bytes['partitions'][0]
    assert int(pb_byte['size'].split('B')[0]) == partition['size']
    assert int(pb_byte['start'].split('B')[0]) == partition['start']
    assert int(pb_byte['end'].split('B')[0]) == partition['end']

    # validate our API shows proper start/end sizes in sectors
    pb_sect = parted_sectors['partitions'][0]
    assert int(pb_sect['start_sector'].split('s')[0]) == partition['start_sector']
    assert int(pb_sect['end_sector'].split('s')[0]) == partition['end_sector']

    # verify wipe disk should removes partition labels
    call('disk.wipe', partition['disk'])
    # the partitions are removed
    new_parts = call('disk.list_partitions', partitions['disk'])
    assert len(new_parts) == 0, new_parts

    # sanity check, make sure parted doesn't see partitions either
    parted_parts = json.loads(ssh(f'parted {partition["path"]} unit s p --json'))['disk']
    assert 'partitions' not in parted_parts, parted_parts
