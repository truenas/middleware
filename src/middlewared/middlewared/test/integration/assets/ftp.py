import contextlib
from types import SimpleNamespace

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh


@contextlib.contextmanager
def ftp_server(config=None):
    if config is not None:
        call("ftp.update", config)
    call("service.control", "START", "ftp", job=True)

    try:
        yield
    finally:
        call("service.control", "STOP", "ftp", job=True)


@contextlib.contextmanager
def anonymous_ftp_server(config=None, dataset_name="anonftp"):
    config = config or {}

    with dataset(dataset_name) as ds:
        path = f"/mnt/{ds}"
        ssh(f"chmod 777 {path}")
        with ftp_server({
            "onlyanonymous": True,
            "anonpath": path,
            "onlylocal": False,
            **config,
        }):
            yield SimpleNamespace(dataset=ds, username="anonymous", password="")


@contextlib.contextmanager
def ftp_server_with_user_account(config=None):
    config = config or {}
    ftp_id = call("group.query", [["name", "=", "ftp"], ['local', '=', True]], {"get": True})["id"]

    with dataset("ftptest") as ds:
        with user({
            "username": "ftptest",
            "group_create": True,
            "home": f"/mnt/{ds}",
            "full_name": "FTP Test",
            "password": "pass",
            "home_create": False,
            "groups": [ftp_id],
        }):
            with ftp_server({
                "onlyanonymous": False,
                "anonpath": None,
                "onlylocal": True,
                **config,
            }):
                yield SimpleNamespace(dataset=ds, username="ftptest", password="pass")
