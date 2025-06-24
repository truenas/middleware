from middlewared.test.integration.utils import client

OLDEST_VERSION = "v25.04.0"


def test_account():
    with client(version=OLDEST_VERSION) as c:
        c.call("user.query")
