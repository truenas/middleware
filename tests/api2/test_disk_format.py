import copy
import json
import time

from middlewared.test.integration.utils import call, ssh

"""
We now use 'sgdisk' to partition disks.
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


def get_partition_info(disk_path):
    # By the time this is called, the disk has been formatted
    # but the kernel might not have been made fully aware of the changes
    # so let's retry a bit before failing
    for i in range(10):
        psectors = json.loads(ssh(f'sfdisk --json {disk_path}'))['partitiontable']
        if psectors.get('partitions') is None:
            time.sleep(1)
        else:
            break
    else:
        assert False, f'sfdisk tool failed to find partitions (in sectors) on {disk_path!r} ({psectors!r})'

    # Now pickup the end sector (rather than calc it)
    end_sectors = {}
    result = ssh(f"sfdisk -l --output Device,End {disk_path} | grep -A20 '^Device' | grep -v '^Device'")
    for line in result.splitlines():
        if line:
            try:
                device, endsector = line.split()
                end_sectors[device] = int(endsector)
            except ValueError:
                continue
    for partition in psectors['partitions']:
        try:
            partition['end'] = end_sectors[partition['node']]
        except KeyError:
            continue

    # Unlike parted, sfdisk only works with sectors.  Calculate bytes
    pbytes = copy.deepcopy(psectors)
    sectorsize = pbytes['sectorsize']
    for partition in pbytes['partitions']:
        partition['start'] *= sectorsize
        # Apparently 'end' is the last byte in that last sector
        partition['end'] = (partition['end'] * sectorsize) + (sectorsize - 1)
        partition['size'] *= sectorsize
    pbytes['units'] = 'bytes'
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

    # We now use sgdisk to format a drive so let's
    # validate our API matches sfdisk output (NOTE:
    # we check both bytes and sectors)
    sfdisk_bytes, sfdisk_sectors = get_partition_info(f'/dev/{unused[0]["name"]}')

    # sanity check (make sure sfdisk shows same number of partitions)
    assert len(sfdisk_bytes['partitions']) == len(partitions), sfdisk_bytes['partitions']
    assert len(sfdisk_sectors['partitions']) == len(partitions), sfdisk_sectors['partitions']

    # validate our API shows proper start/end sizes in bytes
    pbyte = sfdisk_bytes['partitions'][0]
    assert pbyte['size'] == partition['size']
    assert pbyte['start'] == partition['start']
    assert pbyte['end'] == partition['end']

    # validate our API shows proper start/end sizes in sectors
    psect = sfdisk_sectors['partitions'][0]
    assert psect['start'] == partition['start_sector']
    assert psect['end'] == partition['end_sector']

    # verify wipe disk should removes partition labels
    call('disk.wipe', partition['disk'], 'QUICK', job=True)
    # the partitions are removed
    new_parts = call('disk.list_partitions', partition['disk'])
    assert len(new_parts) == 0, new_parts

    # sanity check, make sure sfdisk doesn't see partitions either
    result = ssh(f'sfdisk --json /dev/{unused[0]["name"]}', check=False, complete_response=True)
    assert 'does not contain a recognized partition table' in result["stderr"]
