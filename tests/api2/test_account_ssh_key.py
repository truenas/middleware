from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh


def test_account_create_update_ssh_key_in_existing_dir():
    with dataset("home") as ds:
        homedir = f"/mnt/{ds}"
        with user({
            "username": "test",
            "full_name": "Test",
            "home": homedir,
            "password": "test1234",
            "group_create": True,
            "sshpubkey": "old",
        }) as u:
            call("user.delete", u["id"])

            with user({
                "username": "test",
                "full_name": "Test",
                "home": homedir,
                "password": "test1234",
                "group_create": True,
                "sshpubkey": "new",
            }) as u:
                u = call("user.get_instance", u["id"])
                assert u["sshpubkey"] == "new"


def test_account_update_ssh_key_and_set_homedir():
    with dataset("home") as ds:
        homedir = f"/mnt/{ds}"

        with user({
            "username": "test",
            "full_name": "Test",
            "password": "test1234",
            "group_create": True,
        }) as u:
            call("user.update", u["id"], {
                "home": homedir,
                "sshpubkey": "new",
            })

            u = call("user.get_instance", u["id"])
            assert u["sshpubkey"] == "new"


def test_account_sets_ssh_key_on_user_create():
    with dataset("home") as ds:
        homedir = f"/mnt/{ds}"

        with user({
            "username": "test",
            "full_name": "Test",
            "home": homedir,
            "password": "test1234",
            "group_create": True,
            "sshpubkey": "old",
        }):
            assert ssh(f"cat {homedir}/test/.ssh/authorized_keys") == "old\n"


def test_account_delete_ssh_key_on_user_delete():
    with dataset("home") as ds:
        homedir = f"/mnt/{ds}"

        with user({
            "username": "test",
            "full_name": "Test",
            "home": homedir,
            "password": "test1234",
            "group_create": True,
            "sshpubkey": "old",
        }) as u:
            call("user.delete", u["id"])

            assert ssh(f"cat {homedir}/test/.ssh/authorized_keys", check=False) == ""
