from middlewared.service import Service
from middlewared.utils.path import is_child


class KubernetesStorageService(Service):

    class Config:
        namespace = 'k8s.storage'
        private = True

    async def get_resources_consuming_host_path(self):
        resources = {'deployment': [], 'statefulset': []}
        locked_datasets = await self.middleware.call('zfs.dataset.locked_datasets')
        for r_type in resources:
            for resource in await self.middleware.call(
                f'k8s.{r_type}.query', [['spec.template.spec.volumes', '!=', []]]
            ):
                host_paths = [
                    v['host_path']['path'] for v in resource['spec']['template']['spec']['volumes']
                    if (v.get('host_path') or {}).get('path')
                ]
                if host_paths:
                    resource.update({
                        'host_paths': host_paths,
                        'consumes_locked_paths': any(
                            any(is_child(p, d['mountpoint']) for d in locked_datasets if d['mountpoint'])
                            for p in host_paths
                        ),
                    })
                    resources[r_type].append(resource)
        return resources
