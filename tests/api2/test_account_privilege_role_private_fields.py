import contextlib

import pytest

from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.keychain import ssh_keypair
from middlewared.test.integration.utils import call

REDACTED = "********"


@pytest.fixture(scope="module")
def readonly_client():
    with unprivileged_user_client(["READONLY"]) as c:
        yield c


@contextlib.contextmanager
def wrap(id):
    yield id


@contextlib.contextmanager
def disk():
    disks = call("disk.query")
    yield disks[0]["identifier"]


@contextlib.contextmanager
def keychaincredential():
    with ssh_keypair() as k:
        yield k["id"]


@pytest.mark.parametrize("how", ["multiple", "single", "get_instance"])
@pytest.mark.parametrize("service,id,options,redacted_fields", (
    ("disk", disk, {"extra": {"passwords": True}}, ["passwd"]),
    ("user", 1, {}, ["unixhash", "smbhash"]),
    ("keychaincredential", keychaincredential, {}, ["attributes"]),
))
def test_crud(readonly_client, how, service, id, options, redacted_fields):
    identifier = "id" if service != "disk" else "identifier"

    with (id() if callable(id) else wrap(id)) as id:
        if how == "multiple":
            result = readonly_client.call(f"{service}.query", [[identifier, "=", id]], options)[0]
        elif how == "single":
            result = readonly_client.call(f"{service}.query", [[identifier, "=", id]], {**options, "get": True})
        elif how == "get_instance":
            result = readonly_client.call(f"{service}.get_instance", id, options)
        else:
            assert False

        for k in redacted_fields:
            assert result[k] == REDACTED


@pytest.mark.parametrize("service,redacted_fields", (
    ("ldap", ["bindpw"]),
    ("mail", ["pass", "oauth"]),
))
def test_config(readonly_client, service, redacted_fields):
    result = readonly_client.call(f"{service}.config")

    for k in redacted_fields:
        assert result[k] == REDACTED
