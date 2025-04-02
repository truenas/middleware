import re

from middlewared.test.integration.utils import session, url


def test_versions():
    with session() as s:
        versions = s.get(f"{url()}/api/versions").json()
        assert isinstance(versions, list)
        assert len(versions) > 0
        assert all(v == "v24.10" or re.match("^v[0-9]{2}\.(04|10)\.[0-9]$", v) for v in versions), versions
