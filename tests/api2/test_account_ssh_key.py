import re

import pytest

from middlewared.service_exception import ValidationErrors
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


@pytest.fixture(scope="module")
def keypair():
    return call("keychaincredential.generate_ssh_key_pair")


def test_account_create_ssh_key_rejected_when_home_parent_not_traversable(keypair):
    """sshd reads authorized_keys as the user itself, so a home directory the user cannot reach
    makes the key useless. Setting one has to be rejected instead of silently doing nothing."""
    with dataset("home") as ds:
        parent = f"/mnt/{ds}/parent"
        ssh(f"mkdir -m 700 {parent}")

        errmsg = (
            f"User 'keyuser' is not allowed to access '{parent}' (it is mode 700, owned by uid 0 and gid 0). "
            f"OpenSSH will reject the public key. Please set permissions that allow the user to traverse every "
            f"directory leading to '{parent}/keyuser'."
        )
        with pytest.raises(ValidationErrors, match=re.escape(errmsg)):
            with user({
                "username": "keyuser",
                "full_name": "Key User",
                "group_create": True,
                "password": "test1234",
                "home": parent,
                "sshpubkey": keypair["public_key"],
            }):
                pass

        # the rejected user.create must not leave the group or the home directory behind
        assert call("group.query", [["group", "=", "keyuser"], ["local", "=", True]]) == []
        assert ssh(f"ls -A {parent}") == ""


def test_account_update_ssh_key_rejected_when_home_parent_not_traversable(keypair):
    with dataset("home") as ds:
        parent = f"/mnt/{ds}/parent"
        ssh(f"mkdir -m 700 {parent}")

        with user({
            "username": "keyuser",
            "full_name": "Key User",
            "group_create": True,
            "password": "test1234",
            "home": parent,
        }) as u:
            errmsg = (
                f"User 'keyuser' is not allowed to access '{parent}' (it is mode 700, owned by uid 0 and gid 0). "
                f"OpenSSH will reject the public key. Please set permissions that allow the user to traverse every "
                f"directory leading to '{parent}/keyuser'."
            )
            with pytest.raises(ValidationErrors, match=re.escape(errmsg)):
                call("user.update", u["id"], {"sshpubkey": keypair["public_key"]})

            assert call("user.get_instance", u["id"])["sshpubkey"] is None

            # opening up the parent directory makes the key acceptable
            ssh(f"chmod 755 {parent}")
            call("user.update", u["id"], {"sshpubkey": keypair["public_key"]})


def test_account_create_ssh_key_rejected_for_world_writable_home(keypair):
    """sshd `StrictModes` refuses an authorized_keys file that lives in a world-writable home
    directory, so the mode the home directory is about to be given has to be checked too."""
    with dataset("home") as ds:
        errmsg = (
            f"Home directory '/mnt/{ds}/keyuser' is world-writable (mode 777). OpenSSH will reject the public "
            f"key. Please set correct home directory permissions."
        )
        with pytest.raises(ValidationErrors, match=re.escape(errmsg)):
            with user({
                "username": "keyuser",
                "full_name": "Key User",
                "group_create": True,
                "password": "test1234",
                "home": f"/mnt/{ds}",
                "home_mode": "777",
                "sshpubkey": keypair["public_key"],
            }):
                pass


def test_account_update_ssh_key_rejected_for_world_writable_home(keypair):
    """The home directory mode an update inherits has to be checked as well, not only the one an
    update sets explicitly."""
    with dataset("home") as ds:
        with user({
            "username": "keyuser",
            "full_name": "Key User",
            "group_create": True,
            "password": "test1234",
            "home": f"/mnt/{ds}",
        }) as u:
            home = call("user.get_instance", u["id"])["home"]
            ssh(f"chmod 777 {home}")

            errmsg = (
                f"Home directory '{home}' is world-writable (mode 777). OpenSSH will reject the public key. "
                f"Please set correct home directory permissions."
            )
            with pytest.raises(ValidationErrors, match=re.escape(errmsg)):
                call("user.update", u["id"], {"sshpubkey": keypair["public_key"]})


def test_account_update_ssh_key_rejected_when_home_owned_by_another_user(keypair):
    """sshd `StrictModes` refuses an authorized_keys file out of a home directory that is owned
    neither by the user nor by root, even when the user can read it."""
    with dataset("home") as ds:
        with user({
            "username": "keyuser",
            "full_name": "Key User",
            "group_create": True,
            "password": "test1234",
            "home": f"/mnt/{ds}",
        }) as u:
            home = call("user.get_instance", u["id"])["home"]
            ssh(f"chown 12345:12345 {home}; chmod 755 {home}")

            errmsg = (
                f"Home directory '{home}' is owned by uid 12345, which is neither the user nor root. OpenSSH "
                f"will reject the public key. Please set correct home directory ownership."
            )
            with pytest.raises(ValidationErrors, match=re.escape(errmsg)):
                call("user.update", u["id"], {"sshpubkey": keypair["public_key"]})

            # root owning the home directory is fine for sshd
            ssh(f"chown 0:0 {home}")
            call("user.update", u["id"], {"sshpubkey": keypair["public_key"]})


def test_account_update_ssh_key_and_home_mode_at_once(keypair):
    """A call that repairs the home directory mode and sets a public key at the same time must
    be judged on the mode it is setting, not on the one it is replacing."""
    with dataset("home") as ds:
        with user({
            "username": "keyuser",
            "full_name": "Key User",
            "group_create": True,
            "password": "test1234",
            "home": f"/mnt/{ds}",
            "home_mode": "777",
        }) as u:
            call("user.update", u["id"], {
                "home_mode": "700",
                "sshpubkey": keypair["public_key"],
            })

            assert call("user.get_instance", u["id"])["sshpubkey"] == keypair["public_key"].strip()
