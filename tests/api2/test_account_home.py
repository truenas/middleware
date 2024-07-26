from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


def test_chown_on_update():
    with dataset("unpriv_homedir") as homedir:
        with user({
            "username": "unpriv",
            "full_name": "unpriv",
            "group_create": True,
            "password": "pass",
        }) as u:
            path = f"/mnt/{homedir}"

            call("user.update", u["id"], {"home": path})

            assert {
                "user": "unpriv",
                "group": "unpriv",
            }.items() < call("filesystem.stat", path).items()
