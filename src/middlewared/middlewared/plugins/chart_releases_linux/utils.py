import enum
import os

from middlewared.utils import run as _run


CHART_NAMESPACE_PREFIX = 'ix-'
RESERVED_NAMES = [
    ('ixExternalInterfacesConfiguration', list),
    ('ixExternalInterfacesConfigurationNames', list),
    ('ixVolumes', list),
]


class Resources(enum.Enum):
    CRONJOB = 'cronjobs'
    DEPLOYMENT = 'deployments'
    JOB = 'jobs'
    PERSISTENT_VOLUME_CLAIM = 'persistent_volume_claims'
    POD = 'pods'
    STATEFULSET = 'statefulsets'


def get_namespace(release_name):
    return f'{CHART_NAMESPACE_PREFIX}{release_name}'


async def run(*args, **kwargs):
    kwargs['env'] = dict(os.environ, KUBECONFIG='/etc/rancher/k3s/k3s.yaml')
    return await _run(*args, **kwargs)


async def get_storage_class_name(release):
    return f'ix-storage-class-{release}'


def get_network_attachment_definition_name(release, count):
    return f'ix-{release}-{count}'
