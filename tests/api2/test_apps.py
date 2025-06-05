import pytest

from middlewared.test.integration.utils import call, client
from middlewared.test.integration.assets.apps import app
from middlewared.test.integration.assets.docker import docker
from middlewared.test.integration.assets.pool import another_pool
from truenas_api_client import ValidationErrors


CUSTOM_CONFIG = {
    'services': {
        'actual_budget': {
            'user': '568:568',
            'image': 'actualbudget/actual-server:24.10.1',
            'restart': 'unless-stopped',
            'deploy': {
                'resources': {
                    'limits': {
                        'cpus': '2',
                        'memory': '4096M'
                    }
                }
            },
            'devices': [],
            'depends_on': {
                'permissions': {
                    'condition': 'service_completed_successfully'
                }
            },
            'cap_drop': ['ALL'],
            'security_opt': ['no-new-privileges'],
            'healthcheck': {
                'interval': '10s',
                'retries': 30,
                'start_period': '10s',
                'test': (
                    "/bin/bash -c 'exec {health_check_fd}< /dev/tcp/127.0.0.1/31012 "
                    "&& echo -e 'GET /health HTTP/1.1\\r\\nHost: 127.0.0.1\\r\\n"
                    "Connection: close\\r\\n\\r\\n' >&$$health_check_fd && "
                    "cat <&$$health_check_fd'"
                ),
                'timeout': '5s'
            },
            'environment': {
                'ACTUAL_HOSTNAME': '0.0.0.0',
                'ACTUAL_PORT': '31012',
                'ACTUAL_SERVER_FILES': '/data/server-files',
                'ACTUAL_USER_FILES': '/data/user-files',
                'GID': '568',
                'GROUP_ID': '568',
                'NODE_ENV': 'production',
                'PGID': '568',
                'PUID': '568',
                'TZ': 'Etc/UTC',
                'UID': '568',
                'USER_ID': '568'
            },
            'ports': [
                {
                    'host_ip': '0.0.0.0',
                    'mode': 'ingress',
                    'protocol': 'tcp',
                    'published': 31012,
                    'target': 31012
                }
            ]
        },
        'permissions': {
            'command': [
                '''
                function process_dir() {
                    local dir=$$1
                    local mode=$$2
                    local uid=$$3
                    local gid=$$4
                    local chmod=$$5
                    local is_temporary=$$6
                    # Process directory logic here...
                }
                process_dir /mnt/actual_budget/config check 568 568 false false
                '''
            ],
            'deploy': {
                'resources': {
                    'limits': {
                        'cpus': '1.0',
                        'memory': '512m'
                    }
                }
            },
            'entrypoint': ['bash', '-c'],
            'image': 'bash',
            'user': 'root'
        }
    },
    'x-portals': [
        {
            'host': '0.0.0.0',
            'name': 'Web UI',
            'path': '/',
            'port': 31012,
            'scheme': 'http'
        }
    ],
    'x-notes': '''# Welcome to TrueNAS SCALE

    Thank you for installing Actual Budget!

    ## Documentation
    Documentation for Actual Budget can be found at https://www.truenas.com/docs.

    ## Bug reports
    If you find a bug in this app, please file an issue at
    https://ixsystems.atlassian.net or https://github.com/truenas/apps.

    ## Feature requests or improvements
    If you find a feature request for this app, please file an issue at
    https://ixsystems.atlassian.net or https://github.com/truenas/apps.
    '''
}

INVALID_YAML = '''
services:
  actual_budget
    user: 568:568
    image: actualbudget/actual-server:24.10.1
    restart: unless-stopped
    deploy:
      resources: {'limits': {'cpus': '2', 'memory': '4096M'}}
    devices: []
    depends_on:
      permissions:
        condition: service_completed_successfully
    cap_drop: ['ALL']
    security_opt: ['no-new-privileges']
'''


@pytest.fixture(scope='module')
def docker_pool():
    with another_pool() as pool:
        with docker(pool) as docker_config:
            yield docker_config


def test_create_catalog_app(docker_pool):
    with app('actual-budget', {
        'train': 'community',
        'catalog_app': 'actual-budget',
    }, {'remove_images': False}) as app_info:
        assert app_info['name'] == 'actual-budget', app_info
        assert app_info['state'] == 'DEPLOYING', app_info
        volume_ds = call('app.get_app_volume_ds', 'actual-budget')
        assert volume_ds is not None, volume_ds


def test_create_custom_app(docker_pool):
    with app('custom-budget', {
        'custom_app': True,
        'custom_compose_config': CUSTOM_CONFIG,
    }, {'remove_images': False}) as app_info:
        assert app_info['name'] == 'custom-budget'
        assert app_info['state'] == 'DEPLOYING'


def test_create_custom_app_validation_error(docker_pool):
    with pytest.raises(ValidationErrors):
        with app('custom-budget', {
            'custom_app': False,
            'custom_compose_config': CUSTOM_CONFIG,
        }, {'remove_images': False}):
            pass


def test_create_custom_app_invalid_yaml(docker_pool):
    with pytest.raises(ValidationErrors):
        with app('custom-budget', {
            'custom_app': True,
            'custom_compose_config': INVALID_YAML,
        }, {'remove_images': False}):
            pass


def test_delete_app_validation_error_for_non_existent_app(docker_pool):
    with pytest.raises(ValidationErrors):
        call('app.delete', 'actual-budget', {'remove_ix_volumes': True, 'remove_images': True}, job=True)


def test_update_app(docker_pool):
    values = {
        'values': {
            'network': {
                'web_port': {
                    'bind_mode': 'published',
                    'host_ips': [],
                    'port_number': 32000
                }
            },
            'resources': {
                'limits': {
                    'memory': 8192
                }
            }
        }
    }
    with app('actual-budget', {
        'train': 'community',
        'catalog_app': 'actual-budget',
    }, {'remove_images': False}) as app_info:
        app_info = call('app.update', app_info['name'], values, job=True)
        assert app_info['active_workloads']['used_ports'][0]['host_ports'][0]['host_port'] == 32000


def test_stop_start_app(docker_pool):
    with app('actual-budget', {
        'train': 'community',
        'catalog_app': 'actual-budget'
    }, {'remove_images': False}):
        # stop running app
        call('app.stop', 'actual-budget', job=True)
        states = call('app.query', [], {'select': ['state']})[0]
        assert states['state'] == 'STOPPED'

        # start stopped app
        call('app.start', 'actual-budget', job=True)
        states = call('app.query', [], {'select': ['state']})[0]
        assert states['state'] in ['RUNNING', 'DEPLOYING']


def test_event_subscribe(docker_pool):
    with client(py_exceptions=False) as c:
        expected_event_type_order = ['ADDED', 'CHANGED']
        expected_event_order = ['STOPPING', 'STOPPED', 'DEPLOYING']
        events = []
        event_types = []

        def callback(event_type, **message):
            nonlocal events, event_types
            if not events or events[-1] != message['fields']['state']:
                events.append(message['fields']['state'])
            if not event_types or event_types[-1] != event_type:
                event_types.append(event_type)

        c.subscribe('app.query', callback, sync=True)

        with app('ipfs', {
            'train': 'community',
            'catalog_app': 'ipfs'
        }):
            events = []
            call('app.stop', 'ipfs', job=True)
            call('app.start', 'ipfs', job=True)
            assert expected_event_order == events

        assert expected_event_type_order == event_types


def test_delete_app_options(docker_pool):
    with app(
        'custom-budget',
        {
            'custom_app': True,
            'custom_compose_config': CUSTOM_CONFIG,
        },
        {'remove_ix_volumes': True, 'remove_images': True}
    ) as app_info:
        assert app_info['name'] == 'custom-budget'
        assert app_info['state'] == 'DEPLOYING'

    app_images = call('app.image.query', [['repo_tags', '=', ['actualbudget/actual-server:24.10.1']]])
    assert len(app_images) == 0
    volume_ds = call('app.get_app_volume_ds', 'custom-budget')
    assert volume_ds is None
