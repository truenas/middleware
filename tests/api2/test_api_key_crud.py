import contextlib

from middlewared.test.integration.utils import call, client


@contextlib.contextmanager
def api_key(allowlist):
    key = call("api_key.create", {"name": "Test API Key", "allowlist": allowlist})
    try:
        yield key
    finally:
        call("api_key.delete", key["id"])


def test_has_key_after_creation_but_not_read():
    api_key = call("api_key.create", {"name": "Test", "allowlist": []})
    try:
        assert "key" in api_key

        instance = call("api_key.get_instance", api_key["id"])
        assert "key" not in instance

        update = call("api_key.update", api_key["id"], {})
        assert "key" not in update
    finally:
        call("api_key.delete", api_key["id"])


def test_api_key_reset():
    with api_key([]) as key:
        with client(auth=None) as c:
            assert c.call("auth.login_with_api_key", key["key"])

        updated = call("api_key.update", key["id"], {"reset": True})

        with client(auth=None) as c:
            assert not c.call("auth.login_with_api_key", key["key"])

        with client(auth=None) as c:
            assert c.call("auth.login_with_api_key", updated["key"])


def test_api_key_delete():
    with api_key([]) as key:
        with client(auth=None) as c:
            assert c.call("auth.login_with_api_key", key["key"])

    with client(auth=None) as c:
        assert not c.call("auth.login_with_api_key", key["key"])
