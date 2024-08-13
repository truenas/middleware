from pathlib import Path

from libzfs import ZFS, ZFSException
from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import Service, ValidationError


def get_zfs_vdev_disks(vdev) -> list:
    if vdev['status'] in ('UNAVAIL', 'OFFLINE'):
        return []

    if vdev['type'] == 'disk':
        return [vdev['path']]
    elif vdev['type'] == 'file':
        return []
    else:
        result = []
        for i in vdev['children']:
            result.extend(get_zfs_vdev_disks(i))
        return result


class ZPoolService(Service):

    class Config:
        namespace = 'zpool'
        private = True
        cli_private = True
        process_pool = True

    def resolve_block_path(self, path, should_resolve):
        if not should_resolve:
            return path

        try:
            dev = Path(path).resolve().name
            resolved = Path(f'/sys/class/block/{dev}').resolve().parent.name
            if resolved == 'block':
                # example zpool status
                # NAME                                        STATE     READ WRITE CKSUM
                # tank                                        DEGRADED     0     0     0
	            #   mirror-0                                  DEGRADED     0     0     0
	            #       sdrh1                                 ONLINE       0     0     0
	            #       7008beaf-4fa3-4c43-ba15-f3d5bea3fe0c  REMOVED      0     0     0
	            #       sda1                                  ONLINE       0     0     0
                return dev
            return resolved
        except Exception:
            return path

    def resolve_block_paths(self, paths, should_resolve):
        if not should_resolve:
            return paths

        return [self.resolve_block_path(i, should_resolve) for i in paths]

    def status_impl(self, pool_name, vdev_type, members, **kwargs):
        real_paths = kwargs.setdefault('real_paths', False)
        final = dict()
        for member in filter(lambda x: x['type'] != 'file', members):
            vdev_disks = self.resolve_block_paths(get_zfs_vdev_disks(member), real_paths)
            if member['type'] == 'disk':
                disk = self.resolve_block_path(member['path'], real_paths)
                final[disk] = {
                    'pool_name': pool_name,
                    'disk_status': member['status'],
                    'disk_read_errors': member['stats']['read_errors'],
                    'disk_write_errors': member['stats']['write_errors'],
                    'disk_checksum_errors': member['stats']['checksum_errors'],
                    'vdev_name': 'stripe',
                    'vdev_type': vdev_type,
                    'vdev_disks': vdev_disks,
                }
            else:
                for i in member['children']:
                    disk = self.resolve_block_path(i['path'], real_paths)
                    final[disk] = {
                        'pool_name': pool_name,
                        'disk_status': i['status'],
                        'disk_read_errors': i['stats']['read_errors'],
                        'disk_write_errors': i['stats']['write_errors'],
                        'disk_checksum_errors': i['stats']['checksum_errors'],
                        'vdev_name': member['name'],
                        'vdev_type': vdev_type,
                        'vdev_disks': vdev_disks,
                    }

        return final

    @accepts(Dict(
        Str('name', required=False, default=None),
        Bool('real_paths', required=False, default=False),
    ))
    def status(self, data):
        """The equivalent of running 'zpool status' from the cli.

        `name`: str the name of the zpool for which to return the status info
        `real_paths`: bool if True, resolve the underlying devices to their
            real device (i.e. /dev/disk/by-id/blah -> /dev/sda1)

        An example of what this returns looks like the following:
            {
              "disks": {
                "/dev/disk/by-partuuid/d9cfa346-8623-402f-9bfe-a8256de902ec": {
                  "pool_name": "evo",
                  "disk_status": "ONLINE",
                  "disk_read_errors": 0,
                  "disk_write_errors": 0,
                  "disk_checksum_errors": 0,
                  "vdev_name": "stripe",
                  "vdev_type": "data",
                  "vdev_disks": [
                    "/dev/disk/by-partuuid/d9cfa346-8623-402f-9bfe-a8256de902ec"
                  ]
                }
              },
              "evo": {
                "log": {},
                "cache": {},
                "spare": {},
                "special": {},
                "dedup": {},
                "data": {
                  "/dev/disk/by-partuuid/d9cfa346-8623-402f-9bfe-a8256de902ec": {
                    "pool_name": "evo",
                    "disk_status": "ONLINE",
                    "disk_read_errors": 0,
                    "disk_write_errors": 0,
                    "disk_checksum_errors": 0,
                    "vdev_name": "stripe",
                    "vdev_type": "data",
                    "vdev_disks": [
                      "/dev/disk/by-partuuid/d9cfa346-8623-402f-9bfe-a8256de902ec"
                    ]
                  }
                }
              }
            }
        """
        with ZFS() as zfs:
            if data['name'] is not None:
                try:
                    pools = [zfs.get(data['name']).groups_asdict()]
                except ZFSException:
                    raise ValidationError('zpool.status', f'{data["name"]!r} not found')
            else:
                pools = [p.groups_asdict() for p in zfs.pools]

        final = {'disks': dict()}
        for pool in pools:
            final[pool['name']] = dict()
            # We do the sorting because when we populate `disks` we want data type disks to be updated last
            for vdev_type in sorted(pool['groups'], key=lambda x: 2 if x == 'data' else 1):
                vdev_members = pool['groups'][vdev_type]
                if not vdev_members:
                    final[pool['name']][vdev_type] = dict()
                    continue

                info = self.status_impl(pool['name'], vdev_type, vdev_members, **data)
                # we key on pool name and disk id because
                # this was designed, primarily, for the
                # `webui.enclosure.dashboard` endpoint
                final[pool['name']][vdev_type] = info
                final['disks'].update(info)

        return final
