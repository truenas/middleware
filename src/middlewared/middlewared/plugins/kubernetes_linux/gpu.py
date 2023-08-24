import os

from middlewared.service import Service
from middlewared.utils import run

from .utils import NVIDIA_RUNTIME_CLASS_NAME


# Contains device plugin daemonsets for supported GPU platforms
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
                    'runtimeClassName': NVIDIA_RUNTIME_CLASS_NAME,
                    'containers': [{
                        'image': 'nvcr.io/nvidia/k8s-device-plugin:v0.13.0',
                        'name': 'nvidia-device-plugin-ctr',
                        'command': ['nvidia-device-plugin', '--config-file', '/etc/config/nvdefault.yaml'],
                        'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
                        'volumeMounts': [
                            {'name': 'device-plugin', 'mountPath': '/var/lib/kubelet/device-plugins'},
                            {'name': 'plugin-config', 'mountPath': '/etc/config'},
                        ]
                    }],
                    'volumes': [
                        {'name': 'device-plugin', 'hostPath': {'path': '/var/lib/kubelet/device-plugins'}},
                        {'name': 'plugin-config', 'configMap': {'name': 'nvidia-device-plugin-config'}},
                    ]
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
                        'args': ["-shared-dev-num", "5"],
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
    },
    'AMD': {
        'apiVersion': 'apps/v1',
        'kind': 'DaemonSet',
        'metadata': {
            'name': 'amdgpu-device-plugin-daemonset',
            'namespace': 'kube-system'
        },
        'spec': {
            'selector': {'matchLabels': {'name': 'amdgpu-dp-ds'}},
            'template': {
                'metadata': {
                    'labels': {'name': 'amdgpu-dp-ds'},
                    'annotations': {'scheduler.alpha.kubernetes.io/critical-pod': ''},
                },
                'spec': {
                    'tolerations': [
                        {'key': 'CriticalAddonsOnly', 'operator': 'Exists'},
                    ],
                    'containers': [{
                        'image': 'rocm/k8s-device-plugin:1.18.0',
                        'name': 'amdgpu-dp-cntr',
                        'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
                        'volumeMounts': [
                            {'name': 'dp', 'mountPath': '/var/lib/kubelet/device-plugins'},
                            {'name': 'sys', 'mountPath': '/sys'},
                        ]
                    }],
                    'volumes': [
                        {'name': 'dp', 'hostPath': {'path': '/var/lib/kubelet/device-plugins'}},
                        {'name': 'sys', 'hostPath': {'path': '/sys'}},
                    ]
                }
            }
        }
    },
}

# Contains configmaps for config files to-be-used by their respective device plugins
GPU_CONFIGMAPS = {
    'NVIDIA': {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {
            'name': 'nvidia-device-plugin-config',
            'namespace': 'kube-system'
        },
        'data': {
            'nvdefault.yaml': """version: v1
sharing:
  timeSlicing:
    renameByDefault: false
    failRequestsGreaterThanOne: true
    resources:
    - name: nvidia.com/gpu
      replicas: 5
"""
        }
    },
}


class KubernetesGPUService(Service):

    class Config:
        private = True
        namespace = 'k8s.gpu'

    async def available_gpus(self):
        node_config = await self.middleware.call('k8s.node.config')
        if not node_config['node_configured']:
            return {}

        found_gpus = await self.get_system_gpus() if (
            await self.middleware.call('kubernetes.config')
        )['configure_gpus'] else set()
        available_gpus = {
            'amd.com/gpu': '0',
            'gpu.intel.com/i915': '0',
            'nvidia.com/gpu': '0',
        }
        for k, v in filter(
            lambda i: (i[0].endswith('/gpu') or i[0].startswith('gpu.intel')) and i[1] != '0',
            node_config['status']['allocatable'].items()
        ):
            available_gpus[k] = v if any(gpu.lower() in k.lower() for gpu in found_gpus) else '0'
        return available_gpus

    async def setup(self):
        try:
            await self.setup_internal()
        except Exception as e:
            # Let's not make this fatal as k8s can function well without GPU
            self.logger.error('Unable to configure GPU for node: %s', e, exc_info=True)

    async def get_system_gpus(self):
        gpus = await self.middleware.call('device.get_info', 'GPU')
        supported_gpus = {'NVIDIA', 'INTEL', 'AMD'}
        return supported_gpus.intersection(set([gpu['vendor'] for gpu in gpus if gpu['available_to_host']]))

    async def setup_internal(self):
        to_remove = set(GPU_CONFIG.keys())
        daemonsets = {
            f'{d["metadata"]["namespace"]}_{d["metadata"]["name"]}': d
            for d in await self.middleware.call('k8s.daemonset.query')
        }
        configmaps = {
            f'{c["metadata"]["namespace"]}_{c["metadata"]["name"]}': c
            for c in await self.middleware.call('k8s.configmap.query')
        }
        k8s_config = await self.middleware.call('kubernetes.config')
        found_gpus = await self.get_system_gpus() if k8s_config['configure_gpus'] else set()
        if found_gpus:
            to_remove = to_remove - found_gpus
            for gpu in found_gpus:
                config = GPU_CONFIG[gpu]
                # We will want to be adding nvidia runtime class if we find a nvidia gpu
                if gpu == 'NVIDIA':
                    await self.configure_nvidia_runtime_class()

                # Configmaps for config-files is optional, only used by nvidia for now
                if GPU_CONFIGMAPS.get(gpu):
                    gpu_configmap_metadata = GPU_CONFIGMAPS[gpu]['metadata']
                    # Nvidia stores it's configuration in a configmap instead of arguments
                    # We make sure to create/update it before creating/updating the plugin itself
                    if f'{gpu_configmap_metadata["namespace"]}_{gpu_configmap_metadata["name"]}' in configmaps:
                        await self.middleware.call(
                            'k8s.configmap.update', gpu_configmap_metadata['name'], {
                                'namespace': gpu_configmap_metadata['namespace'], 'body': GPU_CONFIGMAPS[gpu]
                            }
                        )
                    else:
                        await self.middleware.call(
                            'k8s.configmap.create', {
                                'namespace': gpu_configmap_metadata['namespace'], 'body': GPU_CONFIGMAPS[gpu]
                            }
                        )

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

                if callable(getattr(self, f'setup_{gpu.lower()}_gpu', None)):
                    await self.middleware.call(f'k8s.gpu.setup_{gpu.lower()}_gpu')

        for vendor in to_remove:
            config_metadata = GPU_CONFIG[vendor]['metadata']
            if vendor == 'NVIDIA' and await self.middleware.call(
                'k8s.runtime_class.query', [['metadata.name', '=', NVIDIA_RUNTIME_CLASS_NAME]]
            ):
                await self.middleware.call('k8s.runtime_class.delete', NVIDIA_RUNTIME_CLASS_NAME)

            if f'{config_metadata["namespace"]}_{config_metadata["name"]}' not in daemonsets:
                continue
            await self.middleware.call(
                'k8s.daemonset.delete', config_metadata['name'],
                {'namespace': config_metadata['namespace']}
            )

            # Configmaps for config-files is optional, only used by nvidia for now
            if gpu_config := GPU_CONFIGMAPS.get(vendor):
                if f'{gpu_config["metadata"]["namespace"]}_{gpu_config["metadata"]["name"]}' not in configmaps:
                    continue
                await self.middleware.call(
                    'k8s.configmap.delete', gpu_config['metadata']['name'],
                    {'namespace': gpu_config['metadata']['namespace']}
                )

    async def configure_nvidia_runtime_class(self):
        # Reference: https://github.com/k3s-io/k3s/issues/4391#issuecomment-1233314825
        if not await self.middleware.call(
            'k8s.runtime_class.query', [['metadata.name', '=', NVIDIA_RUNTIME_CLASS_NAME]]
        ):
            await self.middleware.call('k8s.runtime_class.create', {
                'body': {
                    'apiVersion': 'node.k8s.io/v1',
                    'kind': 'RuntimeClass',
                    'metadata': {'name': NVIDIA_RUNTIME_CLASS_NAME},
                    'handler': NVIDIA_RUNTIME_CLASS_NAME,
                }
            })

    async def setup_nvidia_gpu(self):
        if os.path.exists('/dev/nvidia-uvm'):
            return

        for command in (
            ['modprobe', 'nvidia-current-uvm'],
            ['nvidia-modprobe', '-c0', '-u'],
        ):
            cp = await run(command, check=False)
            if cp.returncode:
                self.logger.error(
                    'Failed to setup nvidia gpu, %r command failed with %r error', ' '.join(command), cp.stderr.decode()
                )
                break
