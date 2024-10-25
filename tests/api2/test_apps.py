import pytest

from middlewared.test.integration.utils import call, client
from middlewared.test.integration.assets.apps import create_app
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


@pytest.fixture(scope='session')
def docker_pool():
    with another_pool() as pool:
        yield pool['name']


@pytest.mark.dependency(name='docker_setup')
def test_docker_setup(docker_pool):
    docker_config = call('docker.update', {'pool': docker_pool}, job=True)
    assert docker_config['pool'] == docker_pool, docker_config


@pytest.mark.dependency(depends=['docker_setup'])
def test_create_catalog_app():
    with create_app('actual-budget', {
        'train': 'community',
        'catalog_app': 'actual-budget',
    }) as app:
        assert app['name'] == 'actual-budget', app
        assert app['state'] == 'DEPLOYING', app
        volume_ds = call('app.get_app_volume_ds', 'actual-budget')
        assert volume_ds is not None, volume_ds


@pytest.mark.dependency(depends=['docker_setup'])
def test_create_custom_app():
    with create_app('custom-budget', {
        'custom_app': True,
        'custom_compose_config': CUSTOM_CONFIG,
    }) as app:
        assert app['name'] == 'custom-budget'
        assert app['state'] == 'DEPLOYING'


@pytest.mark.dependency(depends=['docker_setup'])
def test_create_custom_app_validation_error():
    with pytest.raises(ValidationErrors):
        with create_app('custom-budget', {
            'custom_app': False,
            'custom_compose_config': CUSTOM_CONFIG,
        }):
            pass


@pytest.mark.dependency(depends=['docker_setup'])
def test_create_custom_app_invalid_yaml():
    with pytest.raises(ValidationErrors):
        with create_app('custom-budget', {
            'custom_app': True,
            'custom_compose_config': INVALID_YAML,
        }):
            pass


@pytest.mark.dependency(depends=['docker_setup'])
def test_delete_app_validation_error_for_non_existent_app():
    with pytest.raises(ValidationErrors):
        call('app.delete', 'actual-budget', {'remove_ix_volumes': True, 'remove_images': True}, job=True)


@pytest.mark.dependency(depends=['docker_setup'])
def test_delete_app_options():
    with create_app(
        'custom-budget',
        {
            'custom_app': True,
            'custom_compose_config': CUSTOM_CONFIG,
        },
        {'remove_ix_volumes': True, 'remove_images': True}
    ) as app:
        assert app['name'] == 'custom-budget'
        assert app['state'] == 'DEPLOYING'

    app_images = call('app.image.query', [['repo_tags', '=', ['actualbudget/actual-server:24.10.1']]])
    assert len(app_images) == 0
    volume_ds = call('app.get_app_volume_ds', 'custom-budget')
    assert volume_ds is None


@pytest.mark.dependency(depends=['docker_setup'])
def test_update_app():
    values = {
        'values': {
            'network': {
                'web_port': 32000
            },
            'resources': {
                'limits': {
                    'memory': 8192
                }
            }
        }
    }
    with create_app('actual-budget', {
        'train': 'community',
        'catalog_app': 'actual-budget',
    }) as app:
        app = call('app.update', app['name'], values, job=True)
        assert app['active_workloads']['used_ports'][0]['host_ports'][0]['host_port'] == 32000


@pytest.mark.dependency(depends=['docker_setup'])
def test_stop_start_app():
    with create_app('actual-budget', {
        'train': 'community',
        'catalog_app': 'actual-budget'
    }):
        # stop running app
        call('app.stop', 'actual-budget', job=True)
        states = call('app.query', [], {'select': ['state']})[0]
        assert states['state'] == 'STOPPED'

        # start stopped app
        call('app.start', 'actual-budget', job=True)
        states = call('app.query', [], {'select': ['state']})[0]
        assert states['state'] == 'DEPLOYING'


@pytest.mark.dependency(depends=['docker_setup'])
def test_event_subscribe():
    def assert_list_order(event_list, expected_list):
        """
        Assert each event in the expected order as they occur
        """
        expected_index = 0
        filtered_list = []
        for event in event_list:
            if expected_index < len(expected_list) and event == expected_list[expected_index]:
                assert event == expected_list[expected_index]
                filtered_list.append(event)
                expected_index += 1
        return filtered_list

    with client(py_exceptions=False) as c:
        expected_event_type_order = ['ADDED', 'CHANGED']
        expected_event_order = ['STOPPING', 'STOPPED', 'DEPLOYING']
        events = []
        event_types = []

        def callback(event_type, **message):
            if events and events[-1] != message['fields']['state']:
                events.append(message['fields']['state'])
            if event_types and event_types[-1] != event_type:
                event_types.append(event_type)

        c.subscribe('app.query', callback, sync=True)

        with create_app('ipfs', {
            'train': 'community',
            'catalog_app': 'ipfs'
        }):
            events = []
            call('app.stop', 'ipfs', job=True)
            call('app.start', 'ipfs', job=True)
            # filtered_events = assert_list_order(events, expected_event_order)
            assert expected_event_order == events

        filtered_event_types = assert_list_order(event_types, expected_event_type_order)
        assert expected_event_type_order == filtered_event_types


@pytest.mark.dependency(depends=['docker_setup'])
def test_unset_apps():
    docker_config = call('docker.update', {'pool': None}, job=True)
    assert docker_config['pool'] is None, docker_config
