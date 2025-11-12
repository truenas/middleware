"""
Unit tests for external Docker container support in TrueNAS Apps.

Tests the ability to list, query, and collect statistics from Docker containers
deployed outside of TrueNAS Apps (via Docker CLI, Portainer, Dockage, etc.)
"""

import collections
import unittest

from middlewared.plugins.apps.ix_apps.query import list_apps, create_external_app_metadata
from middlewared.plugins.apps.stats_util import normalize_projects_stats


AVAILABLE_MAPPING = {
    'community': {
        'actual-budget': {
            'version': '1.1.13',
            'app_version': '24.10.1'
        },
    }
}

TRUENAS_APP_METADATA = {
    'actual-budget': {
        'custom_app': False,
        'human_version': '24.10.1_1.1.13',
        'metadata': {
            'app_version': '24.10.1',
            'name': 'actual-budget',
            'title': 'Actual Budget',
            'train': 'community',
            'version': '1.1.13'
        },
        'migrated': False,
        'portals': {'Web UI': 'http://0.0.0.0:31012/'},
        'version': '1.1.13'
    }
}

KWARGS_WITH_EXTERNAL = {
    'host_ip': None,
    'retrieve_config': False,
    'image_update_cache': {},
    'include_external': True,
}

KWARGS_WITHOUT_EXTERNAL = {
    'host_ip': None,
    'retrieve_config': False,
    'image_update_cache': {},
    'include_external': False,
}


class TestCreateExternalAppMetadata:
    """Tests for synthetic metadata generation for external containers."""

    def test_create_external_metadata_basic(self):
        """Test creating metadata for a simple external container."""
        container_details = [{
            'image': 'portainer/portainer-ce:latest',
            'service_name': 'portainer',
            'state': 'running',
            'id': 'abc123'
        }]

        metadata = create_external_app_metadata('portainer', container_details)

        assert metadata['metadata']['name'] == 'portainer'
        assert metadata['metadata']['title'] == 'portainer'
        assert metadata['metadata']['train'] == 'external'
        assert metadata['source'] == 'EXTERNAL'
        assert metadata['custom_app'] is True
        assert metadata['human_version'] == 'portainer/portainer-ce:latest'
        assert 'External Docker container' in metadata['metadata']['description']

    def test_create_external_metadata_no_containers(self):
        """Test creating metadata when container details are empty."""
        metadata = create_external_app_metadata('empty-app', [])

        assert metadata['human_version'] == 'unknown'
        assert metadata['metadata']['name'] == 'empty-app'

    def test_create_external_metadata_complex_image(self):
        """Test metadata generation with complex image name."""
        container_details = [{
            'image': 'registry.example.com:5000/namespace/app:v1.2.3',
            'service_name': 'custom-app',
            'state': 'running',
            'id': 'xyz789'
        }]

        metadata = create_external_app_metadata('custom-app', container_details)

        assert metadata['human_version'] == 'registry.example.com:5000/namespace/app:v1.2.3'
        assert 'Image: registry.example.com:5000/namespace/app:v1.2.3' in metadata['notes']


class TestListAppsWithExternalContainers:
    """Tests for listing apps including external Docker containers."""

    @unittest.mock.patch('os.scandir')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.upgrade_available_for_app')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.translate_resources_to_desired_workflow')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.list_resources_by_project')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.get_collective_metadata')
    def test_list_only_external_apps(
        self, mock_metadata, mock_list_resources, mock_translate, mock_upgrade, mock_scandir
    ):
        """Test listing only external containers when include_external=True."""
        mock_metadata.return_value = {}
        mock_list_resources.return_value = collections.defaultdict(None, {
            'portainer': {
                'containers': 1,
                'container_details': [{
                    'service_name': 'portainer',
                    'image': 'portainer/portainer-ce:latest',
                    'state': 'running',
                    'id': 'abc123'
                }],
                'images': ['portainer/portainer-ce:latest']
            }
        })
        mock_translate.return_value = mock_list_resources.return_value['portainer']
        mock_upgrade.return_value = (False, None)
        mock_scandir.return_value.__enter__.return_value = []

        result = list_apps(AVAILABLE_MAPPING, **KWARGS_WITH_EXTERNAL)

        assert len(result) == 1
        assert result[0]['name'] == 'portainer'
        assert result[0]['source'] == 'EXTERNAL'
        assert result[0]['metadata']['train'] == 'external'
        assert result[0]['custom_app'] is True

    @unittest.mock.patch('os.scandir')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.upgrade_available_for_app')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.translate_resources_to_desired_workflow')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.list_resources_by_project')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.get_collective_metadata')
    def test_list_mixed_apps(
        self, mock_metadata, mock_list_resources, mock_translate, mock_upgrade, mock_scandir
    ):
        """Test listing both TrueNAS and external apps together."""
        mock_metadata.return_value = TRUENAS_APP_METADATA
        workloads = {
            'ix-actual-budget': {
                'containers': 1,
                'container_details': [{
                    'service_name': 'actual_budget',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'running',
                    'id': 'truenas123'
                }],
                'images': ['actualbudget/actual-server:24.10.1']
            },
            'portainer': {
                'containers': 1,
                'container_details': [{
                    'service_name': 'portainer',
                    'image': 'portainer/portainer-ce:latest',
                    'state': 'running',
                    'id': 'external123'
                }],
                'images': ['portainer/portainer-ce:latest']
            },
            'nginx-proxy': {
                'containers': 1,
                'container_details': [{
                    'service_name': 'nginx',
                    'image': 'jc21/nginx-proxy-manager:latest',
                    'state': 'running',
                    'id': 'external456'
                }],
                'images': ['jc21/nginx-proxy-manager:latest']
            }
        }
        mock_list_resources.return_value = collections.defaultdict(None, workloads)

        def translate_side_effect(resources):
            for key in workloads:
                if resources == workloads[key]:
                    return workloads[key]
            return {}

        mock_translate.side_effect = translate_side_effect
        mock_upgrade.return_value = (False, None)
        mock_scandir.return_value.__enter__.return_value = []

        result = list_apps(AVAILABLE_MAPPING, **KWARGS_WITH_EXTERNAL)

        # Should have 3 apps: 1 TrueNAS + 2 external
        assert len(result) == 3

        # Find each app type
        truenas_apps = [a for a in result if a.get('source') == 'TRUENAS']
        external_apps = [a for a in result if a.get('source') == 'EXTERNAL']

        assert len(truenas_apps) == 1
        assert len(external_apps) == 2

        # Verify TrueNAS app
        assert truenas_apps[0]['name'] == 'actual-budget'
        assert truenas_apps[0]['custom_app'] is False

        # Verify external apps
        external_names = {a['name'] for a in external_apps}
        assert external_names == {'portainer', 'nginx-proxy'}
        for app in external_apps:
            assert app['custom_app'] is True
            assert app['metadata']['train'] == 'external'

    @unittest.mock.patch('os.scandir')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.upgrade_available_for_app')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.translate_resources_to_desired_workflow')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.list_resources_by_project')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.get_collective_metadata')
    def test_exclude_external_apps(
        self, mock_metadata, mock_list_resources, mock_translate, mock_upgrade, mock_scandir
    ):
        """Test that external apps are excluded when include_external=False."""
        mock_metadata.return_value = TRUENAS_APP_METADATA
        workloads = {
            'ix-actual-budget': {
                'containers': 1,
                'container_details': [{
                    'service_name': 'actual_budget',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'running',
                    'id': 'truenas123'
                }],
                'images': ['actualbudget/actual-server:24.10.1']
            }
        }
        mock_list_resources.return_value = collections.defaultdict(None, workloads)
        mock_translate.return_value = workloads['ix-actual-budget']
        mock_upgrade.return_value = (False, None)
        mock_scandir.return_value.__enter__.return_value = []

        result = list_apps(AVAILABLE_MAPPING, **KWARGS_WITHOUT_EXTERNAL)

        # Should only have TrueNAS apps
        assert len(result) == 1
        assert result[0]['name'] == 'actual-budget'
        assert result[0].get('source') == 'TRUENAS'


class TestExternalAppStatsNormalization:
    """Tests for statistics normalization with external apps."""

    def test_normalize_stats_external_only(self):
        """Test normalizing stats for only external containers."""
        all_stats = {
            'portainer': {
                'cpu_usage': 50000000000,  # 50 billion nanoseconds
                'memory': 134217728,  # 128 MiB
                'networks': {
                    'eth0': {'rx_bytes': 10000, 'tx_bytes': 5000}
                },
                'blkio': {'read': 1048576, 'write': 524288}
            }
        }
        old_stats = {
            'portainer': {
                'cpu_usage': 0,
                'memory': 0,
                'networks': {
                    'eth0': {'rx_bytes': 0, 'tx_bytes': 0}
                },
                'blkio': {'read': 0, 'write': 0}
            }
        }

        with unittest.mock.patch('middlewared.plugins.apps.stats_util.get_collective_metadata') as mock_metadata:
            with unittest.mock.patch('middlewared.plugins.apps.stats_util.cpu_info') as mock_cpu:
                mock_metadata.return_value = {}  # No TrueNAS apps
                mock_cpu.return_value = {'core_count': 4}

                result = normalize_projects_stats(all_stats, old_stats, interval=2)

                assert len(result) == 1
                assert result[0]['app_name'] == 'portainer'
                assert result[0]['memory'] == 134217728
                assert result[0]['blkio']['read'] == 1048576
                assert result[0]['blkio']['write'] == 524288
                assert len(result[0]['networks']) == 1
                assert result[0]['networks'][0]['interface_name'] == 'eth0'

    def test_normalize_stats_mixed_apps(self):
        """Test normalizing stats for both TrueNAS and external apps."""
        all_stats = {
            'ix-actual-budget': {
                'cpu_usage': 100000000000,
                'memory': 268435456,
                'networks': {
                    'eth0': {'rx_bytes': 20000, 'tx_bytes': 10000}
                },
                'blkio': {'read': 2097152, 'write': 1048576}
            },
            'portainer': {
                'cpu_usage': 50000000000,
                'memory': 134217728,
                'networks': {
                    'eth0': {'rx_bytes': 10000, 'tx_bytes': 5000}
                },
                'blkio': {'read': 1048576, 'write': 524288}
            }
        }
        old_stats = {
            'ix-actual-budget': {
                'cpu_usage': 0,
                'memory': 0,
                'networks': {
                    'eth0': {'rx_bytes': 0, 'tx_bytes': 0}
                },
                'blkio': {'read': 0, 'write': 0}
            },
            'portainer': {
                'cpu_usage': 0,
                'memory': 0,
                'networks': {
                    'eth0': {'rx_bytes': 0, 'tx_bytes': 0}
                },
                'blkio': {'read': 0, 'write': 0}
            }
        }

        with unittest.mock.patch('middlewared.plugins.apps.stats_util.get_collective_metadata') as mock_metadata:
            with unittest.mock.patch('middlewared.plugins.apps.stats_util.cpu_info') as mock_cpu:
                mock_metadata.return_value = TRUENAS_APP_METADATA
                mock_cpu.return_value = {'core_count': 4}

                result = normalize_projects_stats(all_stats, old_stats, interval=2)

                # Should have stats for both apps
                assert len(result) == 2

                app_names = {r['app_name'] for r in result}
                assert app_names == {'actual-budget', 'portainer'}

                # Verify TrueNAS app
                truenas_app = next(r for r in result if r['app_name'] == 'actual-budget')
                assert truenas_app['memory'] == 268435456

                # Verify external app
                external_app = next(r for r in result if r['app_name'] == 'portainer')
                assert external_app['memory'] == 134217728

    def test_normalize_stats_external_with_stopped_truenas_app(self):
        """Test that only running apps show stats; stopped TrueNAS apps are not included."""
        all_stats = {
            'portainer': {
                'cpu_usage': 50000000000,
                'memory': 134217728,
                'networks': {
                    'eth0': {'rx_bytes': 10000, 'tx_bytes': 5000}
                },
                'blkio': {'read': 1048576, 'write': 524288}
            }
        }
        old_stats = {
            'portainer': {
                'cpu_usage': 0,
                'memory': 0,
                'networks': {
                    'eth0': {'rx_bytes': 0, 'tx_bytes': 0}
                },
                'blkio': {'read': 0, 'write': 0}
            }
        }

        with unittest.mock.patch('middlewared.plugins.apps.stats_util.get_collective_metadata') as mock_metadata:
            with unittest.mock.patch('middlewared.plugins.apps.stats_util.cpu_info') as mock_cpu:
                # TrueNAS app exists in metadata but not in running stats (stopped)
                mock_metadata.return_value = TRUENAS_APP_METADATA
                mock_cpu.return_value = {'core_count': 4}

                result = normalize_projects_stats(all_stats, old_stats, interval=2)

                # Should only have stats for running containers
                assert len(result) == 1

                # External app should have real stats
                external_app = result[0]
                assert external_app['app_name'] == 'portainer'
                assert external_app['memory'] == 134217728


class TestExternalAppStatesAndEdgeCases:
    """Tests for edge cases and state handling with external apps."""

    @unittest.mock.patch('os.scandir')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.upgrade_available_for_app')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.translate_resources_to_desired_workflow')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.list_resources_by_project')
    @unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.get_collective_metadata')
    def test_external_app_various_states(
        self, mock_metadata, mock_list_resources, mock_translate, mock_upgrade, mock_scandir
    ):
        """Test external apps in various container states."""
        mock_metadata.return_value = {}
        workloads = {
            'running-app': {
                'containers': 1,
                'container_details': [{'service_name': 'app', 'image': 'img:latest', 'state': 'running', 'id': '1'}],
                'images': ['img:latest']
            },
            'crashed-app': {
                'containers': 1,
                'container_details': [{'service_name': 'app', 'image': 'img:latest', 'state': 'crashed', 'id': '2'}],
                'images': ['img:latest']
            },
            'stopped-app': {
                'containers': 1,
                'container_details': [{'service_name': 'app', 'image': 'img:latest', 'state': 'exited', 'id': '3'}],
                'images': ['img:latest']
            }
        }
        mock_list_resources.return_value = collections.defaultdict(None, workloads)

        def translate_side_effect(resources):
            for key in workloads:
                if resources == workloads[key]:
                    return workloads[key]
            return {}

        mock_translate.side_effect = translate_side_effect
        mock_upgrade.return_value = (False, None)
        mock_scandir.return_value.__enter__.return_value = []

        result = list_apps(AVAILABLE_MAPPING, **KWARGS_WITH_EXTERNAL)

        assert len(result) == 3

        states = {r['name']: r['state'] for r in result}
        assert states['running-app'] == 'RUNNING'
        assert states['crashed-app'] == 'CRASHED'
        assert states['stopped-app'] == 'STOPPED'
