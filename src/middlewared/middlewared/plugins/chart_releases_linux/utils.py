import copy
import enum
import os
import yaml

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


# We would like to customize safe dumper here so that when it dumps values, we quote strings
# why we want to do this is for instances when strings like 'y' are treated as boolean true
# by yaml and if we don't dump this enclosed with quotes, helm treats 'y' as true and we get inconsistent
# usage
def initialize_yaml_str_representer():
    yaml.add_representer(
        str, lambda dumper, data: dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"'), yaml.SafeDumper
    )


def get_action_context(release_name):
    return copy.deepcopy({
        'operation': None,
        'isInstall': False,
        'isUpdate': False,
        'isUpgrade': False,
        'storageClassName': get_storage_class_name(release_name),
        'upgradeMetadata': {},
    })


def add_context_to_configuration(config, context_dict):
    if 'global' in config:
        config['global'].update(context_dict)
        config.update(context_dict)
    else:
        config.update({
            'global': context_dict,
            **context_dict
        })
    return config


def get_namespace(release_name):
    return f'{CHART_NAMESPACE_PREFIX}{release_name}'


def get_chart_release_from_namespace(namespace):
    return namespace.split(CHART_NAMESPACE_PREFIX, 1)[-1]


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
