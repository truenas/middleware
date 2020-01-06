import os

from copy import deepcopy

from middlewared.service import Service

from .mirror_base import DiskMirrorBase


class DiskService(Service, DiskMirrorBase):

    def get_mirrors(self):
        mirrors = []
        base_path = '/dev/md'
        for array in os.listdir(base_path) if os.path.exists(base_path) else []:
            mirror_data = deepcopy(self.mirror_base)
            mirror_data.update({
                'name': array,
                'path': os.path.join(base_path, array),
                'real_path': os.path.realpath(os.path.join(base_path, array)),
            })
            for provider in os.listdir(
                os.path.join('/sys/block', mirror_data['path'].split('/')[-1], 'slaves')
            ):
                provider_data = {'name': provider, 'id': provider}
                with open(os.path.join('/sys/class/block', provider, 'partition'), 'r') as f:
                    provider_data['disk'] = provider.rsplit(f.read().strip(), 1)[0].strip()
                mirror_data['providers'].append(provider_data)
            mirrors.append(mirror_data)
        return mirrors
