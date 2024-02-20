from pathlib import Path

from libzfs import ZFS, ZFSException
from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import Service, ValidationError


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
        for member in filter(lambda x: x.type != 'file', members):
            vdev_disks = self.resolve_block_paths(member.disks, real_paths)
            if member.type == 'disk':
                disk = self.resolve_block_path(member.path, real_paths)
                final[disk] = {
                    'pool_name': pool_name,
                    'disk_status': member.status,
                    'vdev_name': 'stripe',
                    'vdev_type': vdev_type,
                    'vdev_disks': vdev_disks,
                }
            else:
                for i in member.children:
                    disk = self.resolve_block_path(i.path, real_paths)
                    final[disk] = {
                        'pool_name': pool_name,
                        'disk_status': i.status,
                        'vdev_name': member.name,
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
          'disks': {
            'sdko': {
              'pool_name': 'sanity',
              'disk_status': 'ONLINE',
              'vdev_name': 'mirror-0',
              'vdev_type': 'data',
              'vdev_disks': [
                'sdko',
                'sdkq'
              ]
            },
            'sdkq': {
              'pool_name': 'sanity',
              'disk_status': 'ONLINE',
              'vdev_name': 'mirror-0',
              'vdev_type': 'data',
              'vdev_disks': [
                'sdko',
                'sdkq'
              ]
            }
          },
          'sanity': {
            'sdko': {
              'pool_name': 'sanity',
              'disk_status': 'ONLINE',
              'vdev_name': 'mirror-0',
              'vdev_type': 'data',
              'vdev_disks': [
                'sdko',
                'sdkq'
              ]
            },
            'sdkq': {
              'pool_name': 'sanity',
              'disk_status': 'ONLINE',
              'vdev_name': 'mirror-0',
              'vdev_type': 'data',
              'vdev_disks': [
                'sdko',
                'sdkq'
              ]
            }
          }
        }
        """
        final = dict()
        with ZFS() as zfs:
            if data['name'] is not None:
                try:
                    pools = [zfs.get(data['name'])]
                except ZFSException:
                    raise ValidationError('zpool.status', f'{data["name"]!r} not found')
            else:
                pools = zfs.pools

            final = {'disks': dict()}
            for pool in pools:
                final[pool.name] = dict()
                for vdev_type, vdev_members in pool.groups.items():
                    info = self.status_impl(pool.name, vdev_type, vdev_members, **data)
                    # we key on pool name and disk id because
                    # this was designed, primarily, for the
                    # `webui.enclosure.dashboard` endpoint
                    final[pool.name].update(info)
                    final['disks'].update(info)

        return final
