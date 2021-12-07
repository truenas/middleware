import contextlib
from types import SimpleNamespace

from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh


@contextlib.contextmanager
def ftp_server(config):
    call("ftp.update", config)
    call("service.start", "ftp")

    try:
        yield
    finally:
        call("service.stop", "ftp")


@contextlib.contextmanager
def anonymous_ftp_server(config=None):
    config = config or {}

    with dataset("anonftp") as ds:
        path = f"/mnt/{ds}"
        ssh(f"chmod 777 {path}")
        with ftp_server({
            "onlyanonymous": True,
            "anonpath": path,
            **config,
        }):
            yield SimpleNamespace(dataset=ds, username="anonymous", password="")


@contextlib.contextmanager
def ftp_server_with_user_account(config=None):
    config = config or {}

    with dataset("ftptest") as ds:
        with group({
            "name": "ftp"
        }) as g:
            with user({
                "username": "ftptest",
                "group_create": True,
                "home": f"/mnt/{ds}",
                "full_name": "FTP Test",
                "password": "pass",
                "groups": [g],
            }):
                with ftp_server({
                    "onlylocal": True,
                    **config,
                }):
                    yield SimpleNamespace(dataset=ds, username="ftptest", password="pass")
