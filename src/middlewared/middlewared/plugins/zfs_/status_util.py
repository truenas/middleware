import json
import subprocess

from middlewared.service import CallError, ValidationError


def get_normalized_disk_info(pool_name: str, disk: dict, vdev_name: str, vdev_type: str, vdev_disks: list) -> dict:
    return {
        'pool_name': pool_name,
        'disk_status': disk['state'],
        'disk_read_errors': disk.get('read_errors', 0),
        'disk_write_errors': disk.get('write_errors', 0),
        'disk_checksum_errors': disk.get('checksum_errors', 0),
        'vdev_name': vdev_name,
        'vdev_type': vdev_type,
        'vdev_disks': vdev_disks,
    }


def get_zfs_vdev_disks(vdev) -> list:
    # We get this safely because of draid based vdevs
    if vdev.get('state') in ('UNAVAIL', 'OFFLINE'):
        return []

    vdev_type = vdev.get('vdev_type')
    if vdev_type == 'disk':
        return [vdev['path']]
    elif vdev_type == 'file':
        return []
    else:
        result = []
        for i in vdev.get('vdevs', {}).values():
            result.extend(get_zfs_vdev_disks(i))
        return result


def get_zpool_status(pool_name: str | None = None) -> dict:
    args = [pool_name] if pool_name else []
    cp = subprocess.run(['zpool', 'status', '-jP', '--json-int'] + args, capture_output=True, check=False)
    if cp.returncode:
        if b'no such pool' in cp.stderr:
            raise ValidationError('zpool.status', f'{pool_name!r} not found')

        raise CallError(f'Failed to get zpool status: {cp.stderr.decode()}')

    return json.loads(cp.stdout)['pools']
