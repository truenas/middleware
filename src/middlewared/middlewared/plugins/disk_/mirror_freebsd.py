import os

from bsd import geom
from copy import deepcopy

from middlewared.service import Service

from .mirror_base import DiskMirrorBase


class DiskService(Service, DiskMirrorBase):

    def get_swap_mirrors(self):
        mirrors = []
        geom.scan()
        klass = geom.class_by_name('MIRROR')
        if not klass:
            return mirrors
        for g in klass.geoms:
            # Skip gmirror that is not swap*
            if not g.name.startswith('swap') or g.name.endswith('.sync'):
                continue
            mirror_data = {
                **deepcopy(self.mirror_base),
                'name': g.name,
                'config_type': g.config.get('Type'),
                'path': os.path.join('/dev/mirror', g.name),
            }
            for c in g.consumers:
                mirror_data['providers'].append({
                    'name': c.provider.name, 'id': c.provider.id, 'disk': c.provider.geom.name
                })
            mirrors.append(mirror_data)

        return mirrors
