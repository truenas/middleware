import re

from middlewared.test.integration.utils import session, url

OLD_VER = re.compile(r'^v[0-9]{2}.(04|10).[0-9]$')
NEW_VER = re.compile(r'^v[0-9]{2}.[0-9].[0-9]$')


def new_version(version):
    """Check if version is vYY.N.N"""
    if NEW_VER.match(version):
        return int(version[1:3]) >= 26
    return False


def test_versions():
    with session() as s:
        versions = s.get(f'{url()}/api/versions').json()
        assert isinstance(versions, list)
        assert len(versions) > 0
        assert all(
            v == 'v24.10' or OLD_VER.match(v) or new_version(v) for v in versions
        ), versions
