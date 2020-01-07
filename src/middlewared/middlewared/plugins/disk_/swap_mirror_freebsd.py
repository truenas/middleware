import os

from bsd import geom
from copy import deepcopy

from middlewared.service import CallError, Service
from middlewared.utils import filter_list, run

from .swap_mirror_base import DiskSwapMirrorBase


class DiskService(Service, DiskSwapMirrorBase):

    async def create_swap_mirror(self, name, options):
        cp = await run('gmirror', 'create', name, *options['paths'], check=False, encoding='utf8')
        if cp.returncode:
            raise CallError(f'Failed to create gmirror {name}: {cp.stderr}')

    async def destroy_swap_mirror(self, name):
        mirror_data = await self.middleware.call('disk.get_swap_mirrors', [['name', '=', name]], {'get': True})
        mirror_name = os.path.join('mirror', name)
        if mirror_data['encrypted_provider']:
            await self.middleware.call('disk.remove_encryption', f'{mirror_name}.eli')

        cp = await run('gmirror', 'destroy', name, check=False, encoding='utf8')
        if cp.returncode:
            raise CallError(f'Failed to destroy mirror {mirror_name}: {cp.stderr}')

    def get_swap_mirrors(self, filters, options):
        mirrors = []
        geom.scan()
        klass = geom.class_by_name('MIRROR')
        if not klass:
            return mirrors
        for g in filter(lambda g: not g.name.endswith('.sync'), klass.geoms):
            mirror_data = {
                **deepcopy(self.mirror_base),
                'name': g.name,
                'config_type': g.config.get('Type') if g.config else None,
                'path': os.path.join('/dev/mirror', g.name),
                'real_path': os.path.join('/dev/mirror', g.name),
            }
            if os.path.exists(f'{mirror_data["path"]}.eli'):
                mirror_data['encrypted_provider'] = f'{mirror_data["path"]}.eli'
            for c in g.consumers:
                mirror_data['providers'].append({
                    'name': c.provider.name, 'id': c.provider.id, 'disk': c.provider.geom.name
                })
            mirrors.append(mirror_data)

        return filter_list(mirrors, filters, options)
