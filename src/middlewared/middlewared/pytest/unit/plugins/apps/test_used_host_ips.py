from unittest.mock import patch

from middlewared.plugins.apps.ix_apps.query import (
    translate_resources_to_desired_workflow, get_default_workload_values, list_apps
)


def test_used_host_ips_empty():
    """Test that used_host_ips is initialized as empty list"""
    result = get_default_workload_values()
    assert 'used_host_ips' in result
    assert result['used_host_ips'] == []


def test_used_host_ips_collection():
    """Test that used_host_ips are collected from container port configurations"""
    app_resources = {
        'containers': [
            {
                'Config': {
                    'Labels': {'com.docker.compose.service': 'web'},
                    'Image': 'nginx:latest'
                },
                'State': {'Status': 'running'},
                'NetworkSettings': {
                    'Ports': {
                        '80/tcp': [
                            {'HostPort': '8080', 'HostIp': '192.168.1.100'},
                            {'HostPort': '8081', 'HostIp': '192.168.1.101'}
                        ],
                        '443/tcp': [
                            {'HostPort': '8443', 'HostIp': '192.168.1.100'}
                        ]
                    }
                },
                'Mounts': [],
                'Id': 'abc123'
            },
            {
                'Config': {
                    'Labels': {'com.docker.compose.service': 'db'},
                    'Image': 'postgres:latest'
                },
                'State': {'Status': 'running'},
                'NetworkSettings': {
                    'Ports': {
                        '5432/tcp': [
                            {'HostPort': '5432', 'HostIp': '192.168.1.102'}
                        ]
                    }
                },
                'Mounts': [],
                'Id': 'def456'
            }
        ],
        'networks': []
    }

    result = translate_resources_to_desired_workflow(app_resources)

    assert 'used_host_ips' in result
    assert sorted(result['used_host_ips']) == ['192.168.1.100', '192.168.1.101', '192.168.1.102']
    assert len(result['used_ports']) == 3  # Number of unique container ports (80, 443, 5432)

    # Verify other fields are populated correctly
    assert result['containers'] == 2
    assert len(result['container_details']) == 2
    assert len(result['images']) == 2


def test_used_host_ips_deduplication():
    """Test that duplicate host IPs are deduplicated"""
    app_resources = {
        'containers': [
            {
                'Config': {
                    'Labels': {'com.docker.compose.service': 'web1'},
                    'Image': 'nginx:latest'
                },
                'State': {'Status': 'running'},
                'NetworkSettings': {
                    'Ports': {
                        '80/tcp': [
                            {'HostPort': '8080', 'HostIp': '0.0.0.0'}
                        ]
                    }
                },
                'Mounts': [],
                'Id': 'abc123'
            },
            {
                'Config': {
                    'Labels': {'com.docker.compose.service': 'web2'},
                    'Image': 'nginx:latest'
                },
                'State': {'Status': 'running'},
                'NetworkSettings': {
                    'Ports': {
                        '80/tcp': [
                            {'HostPort': '8081', 'HostIp': '0.0.0.0'}
                        ]
                    }
                },
                'Mounts': [],
                'Id': 'def456'
            }
        ],
        'networks': []
    }

    result = translate_resources_to_desired_workflow(app_resources)

    assert 'used_host_ips' in result
    assert result['used_host_ips'] == ['0.0.0.0']  # Deduplicated


def test_used_host_ips_no_ports():
    """Test that used_host_ips is empty when no ports are exposed"""
    app_resources = {
        'containers': [
            {
                'Config': {
                    'Labels': {'com.docker.compose.service': 'internal'},
                    'Image': 'alpine:latest'
                },
                'State': {'Status': 'running'},
                'NetworkSettings': {
                    'Ports': {}  # No exposed ports
                },
                'Mounts': [],
                'Id': 'abc123'
            }
        ],
        'networks': []
    }

    result = translate_resources_to_desired_workflow(app_resources)

    assert 'used_host_ips' in result
    assert result['used_host_ips'] == []
    assert result['used_ports'] == []


def test_used_host_ips_with_ipv6():
    """Test that IPv6 addresses are handled correctly"""
    app_resources = {
        'containers': [
            {
                'Config': {
                    'Labels': {'com.docker.compose.service': 'web'},
                    'Image': 'nginx:latest'
                },
                'State': {'Status': 'running'},
                'NetworkSettings': {
                    'Ports': {
                        '80/tcp': [
                            {'HostPort': '8080', 'HostIp': '::1'},
                            {'HostPort': '8081', 'HostIp': '2001:db8::1'}
                        ]
                    }
                },
                'Mounts': [],
                'Id': 'abc123'
            }
        ],
        'networks': []
    }

    result = translate_resources_to_desired_workflow(app_resources)

    assert 'used_host_ips' in result
    assert sorted(result['used_host_ips']) == ['2001:db8::1', '::1']


@patch('middlewared.plugins.apps.ix_apps.query.get_collective_metadata')
@patch('middlewared.plugins.apps.ix_apps.query.list_resources_by_project')
def test_list_apps_includes_used_host_ips(mock_list_resources, mock_metadata):
    """Test that list_apps includes used_host_ips in the response"""
    mock_metadata.return_value = {
        'test-app': {
            'custom_app': False,
            'human_version': '1.0.0',
            'metadata': {
                'name': 'test-app',
                'train': 'community',
                'version': '1.0.0'
            },
            'migrated': False,
            'portals': {},
            'version': '1.0.0'
        }
    }

    mock_list_resources.return_value = {
        'ix-test-app': {
            'containers': [
                {
                    'Config': {
                        'Labels': {'com.docker.compose.service': 'web'},
                        'Image': 'nginx:latest'
                    },
                    'State': {'Status': 'running'},
                    'NetworkSettings': {
                        'Ports': {
                            '80/tcp': [
                                {'HostPort': '8080', 'HostIp': '192.168.1.100'}
                            ]
                        }
                    },
                    'Mounts': [],
                    'Id': 'abc123'
                }
            ],
            'networks': []
        }
    }

    with patch('os.scandir') as mock_scandir:
        mock_scandir.return_value.__enter__.return_value = []

        result = list_apps({}, host_ip='192.168.1.100')

        assert len(result) == 1
        assert result[0]['name'] == 'test-app'
        assert 'active_workloads' in result[0]
        assert 'used_host_ips' in result[0]['active_workloads']
        assert result[0]['active_workloads']['used_host_ips'] == ['192.168.1.100']
