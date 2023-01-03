import copy
import enum
import os

from middlewared.utils import run as _run


CHART_NAMESPACE_PREFIX = 'ix-'
CONTEXT_KEY_NAME = 'ixChartContext'
RESERVED_NAMES = [
    ('ixCertificates', dict),
    ('ixCertificateAuthorities', dict),
    ('ixExternalInterfacesConfiguration', list),
    ('ixExternalInterfacesConfigurationNames', list),
    ('ixVolumes', list),
    (CONTEXT_KEY_NAME, dict),
]


class Resources(enum.Enum):
    CRONJOB = 'cronjobs'
    DEPLOYMENT = 'deployments'
    JOB = 'jobs'
    PERSISTENT_VOLUME_CLAIM = 'persistent_volume_claims'
    POD = 'pods'
    STATEFULSET = 'statefulsets'


def get_action_context(release_name):
    return copy.deepcopy({
        'operation': None,
        'isInstall': False,
        'isUpdate': False,
        'isUpgrade': False,
        'storageClassName': get_storage_class_name(release_name),
        'upgradeMetadata': {},
    })


async def add_context_to_configuration(config, context_dict, middleware, release_name):
    context_dict[CONTEXT_KEY_NAME]['kubernetes_config'] = {
        k: v for k, v in (await middleware.call('kubernetes.config')).items()
        if k in ('cluster_cidr', 'service_cidr', 'cluster_dns_ip')
    }
    if 'global' in config:
        config['global'].update(context_dict)
        config.update(context_dict)
    else:
        config.update({
            'global': context_dict,
            **context_dict
        })
    config['release_name'] = release_name
    return config


def get_namespace(release_name):
    return f'{CHART_NAMESPACE_PREFIX}{release_name}'


def get_chart_release_from_namespace(namespace):
    return namespace.split(CHART_NAMESPACE_PREFIX, 1)[-1]


def safe_to_ignore_path(path: str) -> bool:
    # "/" and "/home/keys/" are added for openebs use only, regular containers can't mount "/" as we have validation
    # already in place by docker elsewhere to prevent that from happening
    if path == '/':
        return True

    for ignore_path in (
        '/etc/',
        '/sys/',
        '/proc/',
        '/var/lib/kubelet/',
        '/dev/',
        '/mnt/',
        '/home/keys/',
        '/run/',
        '/var/run/',
        '/var/lock/',
        '/lock',
        '/usr/share/zoneinfo',  # allow mounting localtime
        '/usr/lib/os-release',  # allow mounting /etc/os-release
    ):
        if path.startswith(ignore_path) or path == ignore_path.removesuffix('/'):
            return True

    return False


def is_ix_volume_path(path: str, dataset: str) -> bool:
    release_path = os.path.join('/mnt', dataset, 'releases')
    if not path.startswith(release_path):
        return False

    app_path = path.replace(release_path, '')
    return path.startswith(os.path.join(release_path, app_path, 'volumes/ix_volumes/'))


def is_ix_namespace(namespace):
    return namespace.startswith(CHART_NAMESPACE_PREFIX)


async def run(*args, **kwargs):
    kwargs['env'] = dict(os.environ, KUBECONFIG='/etc/rancher/k3s/k3s.yaml')
    return await _run(*args, **kwargs)


def get_storage_class_name(release):
    return f'ix-storage-class-{release}'


def get_network_attachment_definition_name(release, count):
    return f'ix-{release}-{count}'


SCALEABLE_RESOURCES = [
    Resources.DEPLOYMENT,
    Resources.STATEFULSET,
]
SCALE_DOWN_ANNOTATION = {
    'key': 'ix\\.upgrade\\.scale\\.down\\.workload',
    'value': ['true', '1'],
}
