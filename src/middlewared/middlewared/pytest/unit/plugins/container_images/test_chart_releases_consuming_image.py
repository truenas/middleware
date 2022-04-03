import pytest

from middlewared.plugins.docker_linux.utils import get_chart_releases_consuming_image


payload = [
    {
        'name': 'plex',
        'resources': {
            'container_images': {
                'plexinc/pms-docker:1.25.3.5409-f11334058': {
                    'id': 'sha256:6749cc56cfe405a3a1a23be95289e374d00ff46ecf3d652e5d9bef42eb775484',
                    'update_available': False
                }
            }
        }
    },
    {
        'name': 'nextcloud',
        'resources': {
            'container_images': {
                'postgres:13.1': {
                    'id': 'sha256:407cece1abfffb1e84b5feb8a763f3773c905c409e52c0ee5f57f33acf0c10c6',
                    'update_available': False
                },
                'nextcloud:23': {
                    'id': 'sha256:2f974665ca82ec404766ad4505a84dedacf418fed11cf4b37ab649827b3d1fc9',
                    'update_available': False
                }
            }
        }
    },
    {
        'name': 'minio',
        'resources': {
            'container_images': {
                'minio/minio:RELEASE.2022-01-25T19-56-04Z': {
                    'id': 'sha256:5999fef911660af13f3d73876ed6cdefc78ddc53a455574ff3a6834f31d68b5c',
                    'update_available': False
                }
            }
        }
    },
    {
        'name': 'miniotest',
        'resources': {
            'container_images': {
                'minio/minio:RELEASE.2022-02-16T00-35-27Z': {
                    'id': 'sha256:1031ccfe95e009180f49144b3634433a9220d5d7a5602583d3c274eff69b0e8d',
                    'update_available': False
                }
            }
        }
    },
    {
        'name': 'odoo',
        'resources': {
            'container_images': {
                'ghcr.io/truecharts/postgresql:v14.1.0@sha256:1eb6ede5a83b4'
                'f6d15633c98b49f813b39519e3233b72e5d212a76f7e29bcd17': {
                    'id': None,
                    'update_available': False
                },
                'tccr.io/truecharts/odoo:v15.0@sha256:d20448fc89fdad7c1208d'
                '2f4882742bb7bd864171ba341806bc574e7c2e92955': {
                    'id': None,
                    'update_available': False
                }
            }
        }
    }
]


@pytest.mark.parametrize('image_ref,chart_releases', [
    (['minio/minio:RELEASE.2022-02-16T00-35-27Z'], ['miniotest']),
    (
        ['ghcr.io/truecharts/postgresql:v14.1.0@sha256:1eb6ede5a83b4f6d15633c98'
         'b49f813b39519e3233b72e5d212a76f7e29bcd17'], ['odoo']
    ),
    (['minio/minio:RELEASE.2022-01-25T19-56-04Z'], ['minio']),
    (['minio/minio:RELEASE.2022-01-25T19-56-04Z', 'minio/minio:RELEASE.2022-02-16T00-35-27Z'], ['minio', 'miniotest']),
    (
        ['ghcr.io/truecharts/postgresql:v14.1.0@sha256:1eb6ede5a83b4f6d15633c98b'
         '49f813b39519e3233b72e5d212a76f7e29bcd17', 'minio/minio:RELEASE.2022-02-16T00-35-27Z'], ['odoo', 'miniotest']
    ),
])
def test_chart_release_images(image_ref, chart_releases):
    actual_results = get_chart_releases_consuming_image(image_ref, payload)
    assert set(actual_results) == set(chart_releases)
