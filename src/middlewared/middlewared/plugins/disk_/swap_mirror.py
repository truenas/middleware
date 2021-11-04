from os.path import exists

from middlewared.service import CallError, Service, private, filterable
from middlewared.utils import filter_list, run


class DiskService(Service):

    @private
    async def create_swap_mirror(self, name, options):
        cp = await run('gmirror', 'create', name, *options['paths'], check=False, encoding='utf8')
        if cp.returncode:
            raise CallError(f'Failed to create gmirror {name}: {cp.stderr}')

    @private
    async def destroy_swap_mirror(self, name):
        mirror_data = await self.middleware.call('disk.get_swap_mirrors', [['name', '=', name]], {'get': True})
        mirror_name = f'mirror/{name}'
        if mirror_data['encrypted_provider']:
            await self.middleware.call('disk.remove_encryption', f'{mirror_name}.eli')

        cp = await run('gmirror', 'destroy', name, check=False, encoding='utf8')
        if cp.returncode:
            raise CallError(f'Failed to destroy mirror {mirror_name}: {cp.stderr}')

    @private
    @filterable
    def get_swap_mirrors(self, filters, options):
        xml = self.middleware.call_sync('geom.get_xml')
        if not xml:
            return []

        mirrors = []
        for i in xml.iterfind('.//class[name="MIRROR"]/geom'):
            try:
                swap_name = i.find('./name').text
                if swap_name.endswith('.sync'):
                    continue
            except AttributeError:
                # if we can't get the name of the swap device,
                # then move on
                continue

            try:
                config_type = i.find('./config/Type').text
            except AttributeError:
                config_type = None

            path = real_path = f'/dev/mirror/{swap_name}'
            eli_path = f'{path}.eli'
            encrypted_provider = eli_path if exists(eli_path) else None

            id = disk_part_name = None
            providers = []
            for c in i.findall('./consumer'):
                id = c.find('./provider').attrib['ref']
                disk_part_name = xml.findall(f'.//provider[@id="{id}"]')[0].find('./name').text
                disk_name = None
                for j in xml.iterfind('.//class[name="PART"]/geom'):
                    if j.find(f'./provider/[name="{disk_part_name}"]'):
                        disk_name = j.find('./name').text
                        break
                providers.append({
                    'name': disk_part_name,
                    'id': id,
                    'disk': disk_name,
                })

            mirrors.append({
                'name': swap_name,
                'config_type': config_type,
                'path': path,
                'real_path': real_path,
                'encrypted_provider': encrypted_provider,
                'providers': providers,
            })

        return filter_list(mirrors, filters, options)
