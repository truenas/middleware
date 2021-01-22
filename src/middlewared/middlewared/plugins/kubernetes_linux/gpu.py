from middlewared.service import Service


GPU_CONFIG = {
    'NVIDIA': {
        'apiVersion': 'apps/v1',
        'kind': 'DaemonSet',
        'metadata': {'name': 'nvidia-device-plugin-daemonset', 'namespace': 'kube-system'},
        'spec': {
            'selector': {'matchLabels': {'name': 'nvidia-device-plugin-ds'}},
            'updateStrategy': {'type': 'RollingUpdate'},
            'template': {
                'metadata': {
                    'annotations': {'scheduler.alpha.kubernetes.io/critical-pod': ''},
                    'labels': {'name': 'nvidia-device-plugin-ds'}
                },
                'spec': {
                    'tolerations': [
                        {'key': 'CriticalAddonsOnly', 'operator': 'Exists'},
                        {'key': 'nvidia.com/gpu', 'operator': 'Exists', 'effect': 'NoSchedule'}
                    ],
                    'priorityClassName': 'system-node-critical',
                    'containers': [{
                        'image': 'nvidia/k8s-device-plugin:1.0.0-beta6',
                        'name': 'nvidia-device-plugin-ctr',
                        'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
                        'volumeMounts': [{'name': 'device-plugin', 'mountPath': '/var/lib/kubelet/device-plugins'}]
                    }],
                    'volumes': [{'name': 'device-plugin', 'hostPath': {'path': '/var/lib/kubelet/device-plugins'}}]
                }
            }
        }
    },
    'INTEL': {
        'apiVersion': 'apps/v1',
        'kind': 'DaemonSet',
        'metadata': {'name': 'intel-gpu-plugin', 'labels': {'app': 'intel-gpu-plugin'}, 'namespace': 'kube-system'},
        'spec': {
            'selector': {'matchLabels': {'app': 'intel-gpu-plugin'}},
            'template': {
                'metadata': {'labels': {'app': 'intel-gpu-plugin'}},
                'spec': {
                    'initContainers': [{
                        'name': 'intel-gpu-initcontainer',
                        'image': 'intel/intel-gpu-initcontainer:0.19.0',
                        'imagePullPolicy': 'IfNotPresent', 'securityContext': {'readOnlyRootFilesystem': True},
                        'volumeMounts': [{
                            'mountPath': '/etc/kubernetes/node-feature-discovery/source.d/', 'name': 'nfd-source-hooks'
                        }]
                    }],
                    'containers': [{
                        'name': 'intel-gpu-plugin',
                        'env': [{'name': 'NODE_NAME', 'valueFrom': {'fieldRef': {'fieldPath': 'spec.nodeName'}}}],
                        'image': 'intel/intel-gpu-plugin:0.19.0',
                        'imagePullPolicy': 'IfNotPresent',
                        'securityContext': {'readOnlyRootFilesystem': True},
                        'volumeMounts': [
                            {'name': 'devfs', 'mountPath': '/dev/dri', 'readOnly': True},
                            {'name': 'sysfs', 'mountPath': '/sys/class/drm', 'readOnly': True},
                            {'name': 'kubeletsockets', 'mountPath': '/var/lib/kubelet/device-plugins'}
                        ]
                    }],
                    'volumes': [
                        {'name': 'devfs', 'hostPath': {'path': '/dev/dri'}},
                        {'name': 'sysfs', 'hostPath': {'path': '/sys/class/drm'}},
                        {'name': 'kubeletsockets', 'hostPath': {'path': '/var/lib/kubelet/device-plugins'}},
                        {
                            'name': 'nfd-source-hooks', 'hostPath': {
                                'path': '/etc/kubernetes/node-feature-discovery/source.d/',
                                'type': 'DirectoryOrCreate'
                            }
                        }
                    ],
                    'nodeSelector': {'kubernetes.io/arch': 'amd64'}
                }
            }
        }
    }
}


class KubernetesGPUService(Service):

    class Config:
        private = True
        namespace = 'k8s.gpu'

    async def available_gpus(self):
        node_config = await self.middleware.call('k8s.node.config')
        if not node_config['node_configured']:
            return {}

        return {
            k: v for k, v in node_config['status']['capacity'].items()
            if k.endswith('/gpu') or k.startswith('gpu.intel')
        }

    async def setup(self):
        try:
            await self.setup_internal()
        except Exception as e:
            # Let's not make this fatal as k8s can function well without GPU
            self.logger.error('Unable to configure GPU for node: %s', e)

    async def setup_internal(self):
        gpus = await self.middleware.call('device.get_info', 'GPU')
        to_remove = set(GPU_CONFIG.keys())
        daemonsets = {
            f'{d["metadata"]["namespace"]}_{d["metadata"]["name"]}': d
            for d in await self.middleware.call('k8s.daemonset.query')
        }

        supported_gpus = {'NVIDIA', 'INTEL'}
        found_gpus = supported_gpus.intersection(set([gpu['vendor'] for gpu in gpus]))
        if found_gpus:
            to_remove = to_remove - found_gpus
            for gpu in found_gpus:
                config = GPU_CONFIG[gpu]
                config_metadata = config['metadata']
                if f'{config_metadata["namespace"]}_{config_metadata["name"]}' in daemonsets:
                    await self.middleware.call(
                        'k8s.daemonset.update', config_metadata['name'], {
                            'namespace': config_metadata['namespace'], 'body': config
                        }
                    )
                else:
                    await self.middleware.call(
                        'k8s.daemonset.create', {'namespace': config_metadata['namespace'], 'body': config}
                    )

        for vendor in to_remove:
            config_metadata = GPU_CONFIG[vendor]['metadata']
            if f'{config_metadata["namespace"]}_{config_metadata["name"]}' not in daemonsets:
                continue
            await self.middleware.call(
                'k8s.daemonset.delete', config_metadata['name'], {'namespace': config_metadata['namespace']}
            )
