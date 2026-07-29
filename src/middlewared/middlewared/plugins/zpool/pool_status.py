import json
from pathlib import Path
import subprocess

from middlewared.service import CallError, ValidationError
from ..zfs_.status_util import get_normalized_disk_info, get_zfs_vdev_disks


def resolve_block_path(self, path, should_resolve):
    if not should_resolve:
        return path

    try:
        dev = Path(path).resolve().name
        resolved = Path(f'/sys/class/block/{dev}').resolve().parent.name
        if resolved == 'block':
            # example zpool status
            # NAME                                          STATE     READ WRITE CKSUM
            # tank                                          DEGRADED     0     0     0
            #   mirror-0                                    DEGRADED     0     0     0
            #       sdrh1                                   ONLINE       0     0     0
            #       7008beaf-4fa3-4c43-ba15-f3d5bea3fe0c    REMOVED      0     0     0
            #       sda1                                    ONLINE       0     0     0
            return dev
        return resolved
    except Exception:
        return path


def resolve_block_paths(self, paths, should_resolve):
    if not should_resolve:
        return paths

    return [self.resolve_block_path(i, should_resolve) for i in paths]


def get_zpool_status(pool_name: str | None = None) -> dict:
    args = [pool_name] if pool_name else []
    cp = subprocess.run(['zpool', 'status', '-jP', '--json-int'] + args, capture_output=True, check=False)
    if cp.returncode:
        if b'no such pool' in cp.stderr:
            raise ValidationError('zpool.status', f'{pool_name!r} not found')

        raise CallError(f'Failed to get zpool status: {cp.stderr.decode()}')

    return json.loads(cp.stdout)['pools']


def status_impl(self, pool_name, vdev_type, members, **kwargs):
    real_paths = kwargs.setdefault('real_paths', False)
    final = dict()
    for member in filter(lambda x: x.get('vdev_type') != 'file', members.values()):
        vdev_disks = self.resolve_block_paths(get_zfs_vdev_disks(member), real_paths)
        if member.get('vdev_type') in ('disk', 'dspare'):
            disk = self.resolve_block_path(member['path'], real_paths)
            final[disk] = get_normalized_disk_info(pool_name, member, 'stripe', vdev_type, vdev_disks)
        else:
            for i in member['vdevs'].values():
                if i['vdev_type'] == 'spare':
                    i_vdevs = list(i['vdevs'].values())
                    if not i_vdevs:
                        # An edge case but just covering to be safe
                        continue

                    i = next((e for e in i_vdevs if e['class'] == 'spare'), i_vdevs[0])
                elif i['vdev_type'] == 'replacing':
                    for j in filter(lambda entry: entry.get('path'), list(i['vdevs'].values())):
                        disk = self.resolve_block_path(j['path'], real_paths)
                        final[disk] = get_normalized_disk_info(pool_name, j, member['name'], vdev_type, vdev_disks)
                    continue

                disk = self.resolve_block_path(i['path'], real_paths)
                final[disk] = get_normalized_disk_info(pool_name, i, member['name'], vdev_type, vdev_disks)

    return final
