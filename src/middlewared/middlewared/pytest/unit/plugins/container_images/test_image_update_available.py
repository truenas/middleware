from unittest.mock import patch
from asynctest import Mock

from middlewared.plugins.docker_linux.update_alerts import DockerImagesService
from middlewared.pytest.unit.middleware import Middleware


image_detail = {
    'id': 'sha256:f2a70e6c04c76c0e7bdb6f9fa95f62fd46f8d058d38b1cf0a0590264f7c9a4d0',
    'labels': {
        'architecture': 'x86_64',
        'vendor': 'MinIO Inc <dev@min.io>',
        'version': 'RELEASE.2022-08-25T07-17-05Z'
    },
    'repo_tags': [
        'minio/minio:RELEASE.2022-08-25T07-17-05Z'
    ],
    'repo_digests': [
        'minio/minio@sha256:1811ba43461b1c38a4f5db1fdab826cb3d6eecb1d7d53ff6da8902bb0ee37695'
    ],
    'size': 224978361,
    'created': {
        '$date': 1661389907000
    },
    'dangling': False,
    'update_available': False,
    'system_image': False
}


async def test_image_no_new_update_available():
    with patch('middlewared.plugins.docker_linux.client.DockerClientMixin._get_repo_digest') as get_repo_digest:
        get_repo_digest.return_value = ['sha256:1811ba43461b1c38a4f5db1fdab826cb3d6eecb1d7d53ff6da8902bb0ee37695']
        m = Middleware()
        m['container.image.query'] = Mock(return_value=[image_detail])
        docker = DockerImagesService(m)
        await docker.check_update()
        update = await docker.image_update_cache()
        assert update['minio/minio:RELEASE.2022-08-25T07-17-05Z'] is False


async def test_image_new_update_available():
    with patch('middlewared.plugins.docker_linux.client.DockerClientMixin._get_repo_digest') as get_repo_digest:
        get_repo_digest.return_value = ['sha256:b3d6eecb1d7d53ff6da8902bb0ee376951811a4f5db1fdab826cba43461b1c38']
        m = Middleware()
        m['container.image.query'] = Mock(return_value=[image_detail])
        docker = DockerImagesService(m)
        await docker.check_update()
        update = await docker.image_update_cache()
        assert update['minio/minio:RELEASE.2022-08-25T07-17-05Z'] is True
