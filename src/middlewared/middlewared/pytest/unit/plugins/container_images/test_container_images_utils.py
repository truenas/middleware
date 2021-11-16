import pytest

from middlewared.plugins.docker_linux.utils import normalize_reference


@pytest.mark.parametrize("reference,expected_results", [
    ('redis', {
        'reference': 'redis',
        'image': 'library/redis',
        'tag': 'latest',
        'registry': 'registry-1.docker.io',
        'complete_tag': 'registry-1.docker.io/library/redis:latest',
    }),
    ('redis:12.1', {
        'reference': 'redis:12.1',
        'image': 'library/redis',
        'tag': '12.1',
        'registry': 'registry-1.docker.io',
        'complete_tag': 'registry-1.docker.io/library/redis:12.1',
    }),
    ('redis:12.1', {
        'reference': 'redis:12.1',
        'image': 'library/redis',
        'tag': '12.1',
        'registry': 'registry-1.docker.io',
        'complete_tag': 'registry-1.docker.io/library/redis:12.1',
    }),
    ('redis@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546', {
        'reference': 'redis@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
        'image': 'library/redis',
        'tag': 'sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
        'registry': 'registry-1.docker.io',
        'complete_tag': 'registry-1.docker.io/library/redis@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
    }),
    ('redis:12.1@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546', {
        'reference': 'redis:12.1@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
        'image': 'library/redis',
        'tag': 'sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
        'registry': 'registry-1.docker.io',
        'complete_tag': 'registry-1.docker.io/library/redis@sha256:54ee15a0b0d2c661d46b9bfbf55b181f9a4e7ddf8bf693eec5703dac2c0f5546',
    }),
    ('ghcr.io/k8s-at-home/transmission', {
        'reference': 'ghcr.io/k8s-at-home/transmission',
        'image': 'k8s-at-home/transmission',
        'tag': 'latest',
        'registry': 'ghcr.io',
        'complete_tag': 'ghcr.io/k8s-at-home/transmission:latest',
    }),
    ('ghcr.io/k8s-at-home/transmission:v3.00', {
        'reference': 'ghcr.io/k8s-at-home/transmission:v3.00',
        'image': 'k8s-at-home/transmission',
        'tag': 'v3.00',
        'registry': 'ghcr.io',
        'complete_tag': 'ghcr.io/k8s-at-home/transmission:v3.00',
    }),
    ('ghcr.io/k8s-at-home/transmission:v3.00@sha256:355f4036c53c782df1957de0e16c63f4298f5b596ae5e621fea8f9ef02dd09e6', {
        'reference': 'ghcr.io/k8s-at-home/transmission:v3.00@sha256:355f4036c53c782df1957de0e16c63f4298f5b596ae5e621fea8f9ef02dd09e6',
        'image': 'k8s-at-home/transmission',
        'tag': 'sha256:355f4036c53c782df1957de0e16c63f4298f5b596ae5e621fea8f9ef02dd09e6',
        'registry': 'ghcr.io',
        'complete_tag': 'ghcr.io/k8s-at-home/transmission@sha256:355f4036c53c782df1957de0e16c63f4298f5b596ae5e621fea8f9ef02dd09e6',
    })
])
def test_normalize_reference(reference, expected_results):
    actual_results = normalize_reference(reference)
    assert actual_results == expected_results
