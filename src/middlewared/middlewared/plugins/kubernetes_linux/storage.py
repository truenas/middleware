from middlewared.service import Service


class KubernetesStorageService(Service):

    class Config:
        namespace = 'k8s.storage'
        private = True

    async def get_resources_consuming_host_path(self):
        resources = {'deployment': [], 'statefulset': []}
        for r_type in resources:
            for resource in await self.middleware.call(
                f'k8s.{r_type}.query', [['spec.template.spec.volumes', '!=', []]]
            ):
                host_paths = [
                    v['host_path']['path'] for v in resource['spec']['template']['spec']['volumes']
                    if (v.get('host_path') or {}).get('path')
                ]
                if host_paths:
                    resource['host_paths'] = host_paths
                    resources[r_type].append(resource)
        return resources
