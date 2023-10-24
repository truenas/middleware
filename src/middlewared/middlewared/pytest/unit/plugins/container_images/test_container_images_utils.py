import pytest

from middlewared.plugins.container_runtime_interface.utils import normalize_reference, normalize_docker_limits_header


@pytest.mark.parametrize("reference,expected_results", [
    ('redis', {
        'reference': 'redis',
        'image': 'library/redis',
        'tag': 'latest',
        'registry': 'registry-1.docker.io',
        'complete_tag': 'registry-1.docker.io/library/redis:latest',
        'reference_is_digest': False,
    }),
    ('redis:12.1', {
        'reference': 'redis:12.1',
        'image': 'library/redis',
        'tag': '12.1',
        'registry': 'registry-1.docker.io',
        'complete_tag': 'registry-1.docker.io/library/redis:12.1',
        'reference_is_digest': False,
    }),
    ('redis:12.1', {
        'reference': 'redis:12.1',
        'image': 'library/redis',
        'tag': '12.1',
        'registry': 'registry-1.docker.io',
        'complete_tag': 'registry-1.docker.io/library/redis:12.1',
        'reference_is_digest': False,
    }),
    ('redis@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546', {
        'reference': 'redis@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
        'image': 'library/redis',
        'tag': 'sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
        'registry': 'registry-1.docker.io',
        'complete_tag': 'registry-1.docker.io/library/redis@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
        'reference_is_digest': True,
    }),
    ('redis:12.1@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546', {
        'reference': 'redis:12.1@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
        'image': 'library/redis',
        'tag': 'sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
        'registry': 'registry-1.docker.io',
        'complete_tag': 'registry-1.docker.io/library/redis@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
        'reference_is_digest': True,
    }),
    ('ghcr.io/k8s-at-home/transmission', {
        'reference': 'ghcr.io/k8s-at-home/transmission',
        'image': 'k8s-at-home/transmission',
        'tag': 'latest',
        'registry': 'ghcr.io',
        'complete_tag': 'ghcr.io/k8s-at-home/transmission:latest',
        'reference_is_digest': False,
    }),
    ('ghcr.io/k8s-at-home/transmission:v3.00', {
        'reference': 'ghcr.io/k8s-at-home/transmission:v3.00',
        'image': 'k8s-at-home/transmission',
        'tag': 'v3.00',
        'registry': 'ghcr.io',
        'complete_tag': 'ghcr.io/k8s-at-home/transmission:v3.00',
        'reference_is_digest': False,
    }),
    ('ghcr.io/k8s-at-home/transmission:v3.00@sha256:355f4036c53c782df1957de0e16c63f4298f5b596ae5e621fea8f9ef02dd09e6', {
        'reference': 'ghcr.io/k8s-at-home/transmission:v3.00@sha256:355f4036c53c782df1957de0e16c63f4298f5b596ae5e621fea8f9ef02dd09e6',
        'image': 'k8s-at-home/transmission',
        'tag': 'sha256:355f4036c53c782df1957de0e16c63f4298f5b596ae5e621fea8f9ef02dd09e6',
        'registry': 'ghcr.io',
        'complete_tag': 'ghcr.io/k8s-at-home/transmission@sha256:355f4036c53c782df1957de0e16c63f4298f5b596ae5e621fea8f9ef02dd09e6',
        'reference_is_digest': True,
    })
])
def test_normalize_reference(reference, expected_results):
    actual_results = normalize_reference(reference)
    assert actual_results == expected_results


@pytest.mark.parametrize('header,expected_response', [
    (
        {
            'ratelimit-limit': '100;w=21600',
            'ratelimit-remaining': '100;w=21600'},
        {
          'total_pull_limit': 100,
          'total_time_limit_in_secs': 21600,
          'remaining_pull_limit': 100,
          'remaining_time_limit_in_secs': 21600,
          'error': None
        }
    ),
    (
        {
            'ratelimit-limit': '100;w=21600',
            'ratelimit-remaining': '97;w=21600'
        },
        {
             'total_pull_limit': 100,
             'total_time_limit_in_secs': 21600,
             'remaining_pull_limit': 97,
             'remaining_time_limit_in_secs': 21600,
             'error': None
        }
    ),
    (
        {
            'ratelimit-limit': '103;w=21',
            'ratelimit-remaining': '68;w=600'
        },
        {
             'total_pull_limit': 103,
             'total_time_limit_in_secs': 21,
             'remaining_pull_limit': 68,
             'remaining_time_limit_in_secs': 600,
             'error': None
        }
    ),
    (
        {
            'ratelimit-limit': '100;w=21600'
        },
        {
            'error': 'Unable to retrieve rate limit information from registry'
        }
    ),
    (
        {
            'ratelimit-remaining': '100;w=21600'
        },
        {
            'error': 'Unable to retrieve rate limit information from registry'
        }
    ),
    (
        {},
        {
            'error': 'Unable to retrieve rate limit information from registry'
        }
    ),
])
def test_normalize_docker_limits_header(header, expected_response):
    assert normalize_docker_limits_header(header) == expected_response
