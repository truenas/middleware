import glob
import os
import contextlib

from middlewared.service import CallError, Service, private
from middlewared.utils import filter_list, run


class DiskService(Service):

    @private
    async def create_swap_mirror(self, name, options):
        extra = options['extra']
        cp = await run(
            'mdadm', '--build', os.path.join('/dev/md', name), f'--level={extra.get("level", 1)}',
            f'--raid-devices={len(options["paths"])}', *options['paths'], encoding='utf8', check=False,
        )
        if cp.returncode:
            raise CallError(f'Failed to create mirror {name}: {cp.stderr}')

    @private
    async def destroy_swap_mirror(self, name):
        mirror = await self.middleware.call('disk.get_swap_mirrors', [['name', '=', name]], {'get': True})
        if mirror['encrypted_provider']:
            await self.middleware.call('disk.remove_encryption', mirror['encrypted_provider'])

        path = mirror['path']
        cp = await run('mdadm', '--stop', path, check=False, encoding='utf8')
        if cp.returncode:
            raise CallError(f'Failed to stop mirror {name!r}: {cp.stderr}')

    @private
    def get_swap_mirrors(self, filters, options):
        mirrors = []
        with contextlib.suppress(FileNotFoundError):
            for array in os.scandir('/dev/md'):
                if not array.name.split(':')[-1].startswith('swap'):
                    continue

                real_path = os.path.realpath(array.name)
                mirror = {
                    'name': array.name,
                    'path': array.path,
                    'real_path': real_path,
                    'encrypted_provider': None,
                    'providers': [],
                }
                if enc_path := glob.glob(f'/sys/block/dm-*/slaves/{real_path.split("/")[-1]}'):
                    mirror['encrypted_provider'] = os.path.join('/dev', enc_path[0].split('/')[3])

                for provider in os.scandir(os.path.join('/sys/block', mirror['real_path'].split('/')[-1], 'slaves')):
                    partition = os.path.join('/sys/class/block', provider.name, 'partition')
                    if os.path.exists(partition):
                        provider_data = {'name': provider.name, 'id': provider.name}
                        with open(partition, 'r') as f:
                            provider_data['disk'] = provider.name.rsplit(f.read().strip(), 1)[0].strip()
                        mirror['providers'].append(provider_data)

                mirrors.append(mirror)

        return filter_list(mirrors, filters, options)
