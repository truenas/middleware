from os import environ
from types import SimpleNamespace


SPACES_CONFIG = {
    'NETMASK': int(environ.get('NETMASK')),
    'INTERFACE': environ.get('INTERFACE'),
    'DEFGW': environ.get('DEFGW'),
    'DNS1': environ.get('DNS1'),
    'ZPOOL_DISK': environ.get('ZPOOL_DISK'),
}

SPACES_ADS = {
    'DOMAIN': environ.get('AD_DOMAIN'),
    'USERNAME': environ.get('AD_USERNAME'),
    'PASSWORD': environ.get('AD_PASSWORD'),
}

TIMEOUTS = {
}

CLEANUP_TEST_DIR = 'tests/cleanup'

SPACES_MEMBERS = [SimpleNamespace(
    node=x,
    dns=environ.get(f'NODE_{x}_DNS'),
    ip=environ.get(f'NODE_{x}_IP'),
    username=environ.get('APIUSER'),
    password=environ.get('APIPASS'),
    zpool=environ.get(f'NODE_{x}_POOL'),
) for x in ('A', 'B', 'C', 'D')]
