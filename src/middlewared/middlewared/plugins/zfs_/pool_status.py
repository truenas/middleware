from pathlib import Path

from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import Service

from .status_util import get_normalized_disk_info, get_zfs_vdev_disks, get_zpool_status


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
        for member in filter(lambda x: x['vdev_type'] != 'file', members.values()):
            vdev_disks = self.resolve_block_paths(get_zfs_vdev_disks(member), real_paths)
            if member['vdev_type'] == 'disk':
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

                    disk = self.resolve_block_path(i['path'], real_paths)
                    final[disk] = get_normalized_disk_info(pool_name, i, member['name'], vdev_type, vdev_disks)

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
                "spares": {},
                "logs": {},
                "dedup": {},
                "special": {},
                "l2cache": {},
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
        pools = get_zpool_status(data.get('name'))

        final = {'disks': dict()}
        for pool_name, pool_info in pools.items():
            final[pool_name] = dict()
            # We need some normalization for data vdev here
            pool_info['data'] = pool_info.get('vdevs', {}).get(pool_name, {}).get('vdevs', {})
            for vdev_type in ('spares', 'logs', 'dedup', 'special', 'l2cache', 'data'):
                vdev_members = pool_info.get(vdev_type, {})
                if not vdev_members:
                    final[pool_name][vdev_type] = dict()
                    continue

                info = self.status_impl(pool_name, vdev_type, vdev_members, **data)
                # we key on pool name and disk id because
                # this was designed, primarily, for the
                # `webui.enclosure.dashboard` endpoint
                final[pool_name][vdev_type] = info
                final['disks'].update(info)

        return final
