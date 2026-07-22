import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool, ssh


def _home_user(home, **overrides):
    """Base payload for a non-SMB local user with an explicit home path."""
    payload = {
        "username": "covhu",
        "full_name": "cov home user",
        "group_create": True,
        "smb": False,
        "password": "test1234",
        "home": home,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# validate_homedir_path - path-shape validation (no dataset required)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "home,substring",
    [
        ("notabsolute", '"Home Directory" must be an absolute path.'),
        ("/etc/hostname", '"Home Directory" cannot be a file.'),
        (f"/mnt/{pool}:bad", '"Home Directory" cannot contain colons (:).'),
        ("/cov_nonexistent_home_dir", '"Home Directory" must begin with /mnt'),
        ("/mnt", 'cannot be at root of "/mnt"'),
    ],
)
def test_home_path_shape(home, substring):
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _home_user(home))

    assert substring in str(ve.value), ve.value


def test_home_on_non_zfs_filesystem():
    # /tmp is tmpfs, not a ZFS dataset.
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _home_user("/tmp"))

    assert "not on a ZFS filesystem" in str(ve.value), ve.value


def test_home_is_pool_mountpoint():
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _home_user(f"/mnt/{pool}"))

    assert "ZFS pool mountpoint" in str(ve.value), ve.value


def test_home_parent_path_missing():
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _home_user("/mnt/cov_missing_pool_xyz/child", home_create=False))

    assert "parent path of specified home directory does not exist" in str(ve.value), ve.value


def test_home_create_parent_missing():
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _home_user("/mnt/cov_missing_pool_xyz", home_create=True))

    assert "does not exist" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# validate_homedir_path - dataset state (read-only / immutable / in-use)
# ---------------------------------------------------------------------------
def test_home_on_readonly_dataset():
    with dataset("cov_ro_home", {"readonly": "ON"}) as ds:
        with pytest.raises(ValidationErrors) as ve:
            call("user.create", _home_user(f"/mnt/{ds}"))

        assert "readonly property set" in str(ve.value), ve.value


def test_home_on_immutable_directory():
    with dataset("cov_immut_home") as ds:
        target = f"/mnt/{ds}/immutdir"
        ssh(f"mkdir {target}")
        ssh(f"chattr +i {target}")
        try:
            with pytest.raises(ValidationErrors) as ve:
                call("user.create", _home_user(target, home_create=False))

            assert "home directory path is immutable" in str(ve.value), ve.value
        finally:
            ssh(f"chattr -i {target}")


def test_home_already_in_use():
    with dataset("cov_shared_home") as ds:
        home = f"/mnt/{ds}"
        with user(_home_user(home, username="covhomeA", home_create=False)):
            with pytest.raises(ValidationErrors) as ve:
                call("user.create", _home_user(home, username="covhomeB", home_create=False))

            assert "homedir already used by" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# setup_homedir - directory creation, skel copy, and rollback
# ---------------------------------------------------------------------------
def test_home_create_makes_directory_and_copies_skel():
    with dataset("cov_new_home") as ds:
        parent = f"/mnt/{ds}"
        with user(_home_user(parent, username="covnew", home_create=True)) as u:
            home = call("user.get_instance", u["id"])["home"]
            assert home == f"{parent}/covnew"
            # created directory is owned by the new user
            assert ssh(f"stat -c %U {home}").strip() == "covnew"
            # skel files were copied into the new home directory
            assert ssh(f"test -f {home}/.bashrc && echo yes").strip() == "yes"


def test_home_use_existing_directory():
    with dataset("cov_existing_home") as ds:
        home = f"/mnt/{ds}"
        with user(_home_user(home, username="covexist", home_create=False)) as u:
            assert call("user.get_instance", u["id"])["home"] == home


def test_home_create_target_is_file_rolls_back():
    with dataset("cov_file_home") as ds:
        parent = f"/mnt/{ds}"
        # A plain file sits where the homedir would be created.
        ssh(f"touch {parent}/covfile")
        with pytest.raises(CallError) as ve:
            call("user.create", _home_user(parent, username="covfile", home_create=True))

        assert "already exists and is not a directory" in ve.value.errmsg
        # the auto-created primary group must have been rolled back
        assert call("group.query", [["name", "=", "covfile"]]) == []


# ---------------------------------------------------------------------------
# recreate_homedir_if_not_exists (on update)
# ---------------------------------------------------------------------------
def test_home_recreated_when_missing():
    with dataset("cov_recreate_home") as ds:
        with user(_home_user(f"/mnt/{ds}", username="covrec", home_create=True)) as u:
            home = call("user.get_instance", u["id"])["home"]
            ssh(f"rm -rf {home}")
            # any update re-creates the missing home directory
            call("user.update", u["id"], {"full_name": "recreated"})
            assert ssh(f"test -d {home} && echo yes").strip() == "yes"


def test_home_recreate_conflicts_with_file():
    with dataset("cov_recreate_conflict") as ds:
        with user(_home_user(f"/mnt/{ds}", username="covrecf", home_create=True)) as u:
            home = call("user.get_instance", u["id"])["home"]
            ssh(f"rm -rf {home}; touch {home}")
            try:
                with pytest.raises((CallError, ValidationErrors)) as ve:
                    call("user.update", u["id"], {"full_name": "conflict"})

                assert "already exists and is not a directory" in str(ve.value)
            finally:
                ssh(f"rm -f {home}")


# ---------------------------------------------------------------------------
# home directory move triggers a background copy (do_home_copy)
# ---------------------------------------------------------------------------
def _wait_home_copy():
    job = call("core.get_jobs", [["method", "=", "user.do_home_copy"]], {"order_by": ["-id"], "get": True})
    call("core.job_wait", job["id"], job=True)


def test_home_move_copies_contents():
    with dataset("cov_move_a") as a, dataset("cov_move_b") as b:
        with user(_home_user(f"/mnt/{a}", username="covmove", home_create=True)) as u:
            old_home = call("user.get_instance", u["id"])["home"]
            ssh(f"touch {old_home}/marker_file")

            call("user.update", u["id"], {"home": f"/mnt/{b}", "home_create": True})
            new_home = call("user.get_instance", u["id"])["home"]
            assert new_home == f"/mnt/{b}/covmove"

            _wait_home_copy()
            assert ssh(f"test -f {new_home}/marker_file && echo yes").strip() == "yes"


def test_home_move_with_explicit_mode():
    # Passing an explicit home_mode alongside the move exercises the
    # `new_mode is not None` branch of do_home_copy.
    with dataset("cov_movemode_a") as a, dataset("cov_movemode_b") as b:
        with user(_home_user(f"/mnt/{a}", username="covmvm", home_create=True)) as u:
            old_home = call("user.get_instance", u["id"])["home"]
            ssh(f"touch {old_home}/marker_file")

            call(
                "user.update",
                u["id"],
                {
                    "home": f"/mnt/{b}",
                    "home_create": True,
                    "home_mode": "750",
                },
            )
            new_home = call("user.get_instance", u["id"])["home"]
            assert new_home == f"/mnt/{b}/covmvm"

            _wait_home_copy()
            assert ssh(f"test -f {new_home}/marker_file && echo yes").strip() == "yes"


# ---------------------------------------------------------------------------
# sshpubkey interactions with the home directory
# ---------------------------------------------------------------------------
def test_sshpubkey_requires_pool_home_on_create():
    # sshpubkey with the default (non-/mnt) home path is rejected in do_create.
    with pytest.raises(ValidationErrors) as ve:
        call(
            "user.create",
            {
                "username": "covsshc",
                "full_name": "cov",
                "group_create": True,
                "smb": False,
                "password": "test1234",
                "sshpubkey": "ssh-rsa AAAAcov",
            },
        )

    assert "the user home directory must be set to a writable path" in str(ve.value), ve.value


def test_sshpubkey_requires_writable_home_on_update():
    with user(
        {
            "username": "covsshu",
            "full_name": "cov",
            "group_create": True,
            "smb": False,
            "password": "test1234",
        }
    ) as u:
        with pytest.raises(ValidationErrors) as ve:
            call("user.update", u["id"], {"sshpubkey": "ssh-rsa AAAAcov"})

        assert "Home directory is not writable" in str(ve.value), ve.value


def test_sshpubkey_written_to_home_directory():
    with dataset("cov_sshkey_home") as ds:
        with user(
            _home_user(
                f"/mnt/{ds}",
                username="covsshw",
                home_create=True,
                sshpubkey="ssh-rsa AAAAcovkey",
            )
        ) as u:
            home = call("user.get_instance", u["id"])["home"]
            assert ssh(f"cat {home}/.ssh/authorized_keys").strip() == "ssh-rsa AAAAcovkey"
            # sshpubkey round-trips through user.query
            assert call("user.get_instance", u["id"])["sshpubkey"] == "ssh-rsa AAAAcovkey"


def test_sshpubkey_removed_when_cleared():
    with dataset("cov_sshkey_clear") as ds:
        with user(
            _home_user(
                f"/mnt/{ds}",
                username="covsshx",
                home_create=True,
                sshpubkey="ssh-rsa AAAAcovkey",
            )
        ) as u:
            home = call("user.get_instance", u["id"])["home"]
            assert ssh(f"cat {home}/.ssh/authorized_keys").strip() == "ssh-rsa AAAAcovkey"

            call("user.update", u["id"], {"sshpubkey": ""})
            assert ssh(f"cat {home}/.ssh/authorized_keys", check=False).strip() == ""


# ---------------------------------------------------------------------------
# home_mode change without a home move (non-recursive setperm)
# ---------------------------------------------------------------------------
def test_home_mode_only_update():
    with dataset("cov_mode_home") as ds:
        with user(_home_user(f"/mnt/{ds}", username="covmode", home_create=True)) as u:
            home = call("user.get_instance", u["id"])["home"]
            call("user.update", u["id"], {"home_mode": "751"})
            assert ssh(f"stat -c %a {home}").strip() == "751"


# ---------------------------------------------------------------------------
# authorized_keys with invalid encoding is tolerated during user.query
# ---------------------------------------------------------------------------
def test_authorized_keys_invalid_encoding():
    with dataset("cov_badkeys") as ds:
        with user(_home_user(f"/mnt/{ds}", username="covbadk", home_create=True)) as u:
            home = call("user.get_instance", u["id"])["home"]
            ssh(f"mkdir -p {home}/.ssh")
            # write invalid UTF-8 bytes into authorized_keys
            ssh(rf"printf '\xff\xfe\x00bad' > {home}/.ssh/authorized_keys")

            # user.query must not raise; the undecodable key is reported as null
            assert call("user.get_instance", u["id"])["sshpubkey"] is None


# ---------------------------------------------------------------------------
# home on a locked (encrypted) dataset
# ---------------------------------------------------------------------------
def test_home_on_locked_encrypted_dataset():
    enc = {
        "encryption_options": {"generate_key": False, "passphrase": "12345678"},
        "encryption": True,
        "inherit_encryption": False,
    }
    with dataset("cov_enc_home", enc) as ds:
        mount = f"/mnt/{ds}"
        call("pool.dataset.lock", ds, job=True)
        # locking makes the mountpoint immutable; clear that so the locked-dataset
        # check (not the immutable check) is what fires
        call("filesystem.set_zfs_attributes", {"path": mount, "zfs_file_attributes": {"immutable": False}}, job=True)

        with pytest.raises(ValidationErrors) as ve:
            call("user.create", _home_user(mount, home_create=False))

        assert "currently encrypted and locked" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# recreate_homedir failure when the parent is read-only
# ---------------------------------------------------------------------------
def test_home_recreate_makedirs_failure():
    with dataset("cov_ro_recreate") as ds:
        with user(_home_user(f"/mnt/{ds}", username="covrofail", home_create=True)) as u:
            home = call("user.get_instance", u["id"])["home"]
            ssh(f"rm -rf {home}")
            ssh(f"zfs set readonly=on {ds}")
            try:
                with pytest.raises((CallError, ValidationErrors)) as ve:
                    call("user.update", u["id"], {"full_name": "cannot recreate"})

                assert "Failed recreating" in str(ve.value)
            finally:
                ssh(f"zfs set readonly=off {ds}")


# ---------------------------------------------------------------------------
# moving a home whose old directory is gone skips the SSH key sync
# ---------------------------------------------------------------------------
def test_sshpubkey_skipped_when_old_home_missing_on_move():
    with dataset("cov_ssh_move_a") as a, dataset("cov_ssh_move_b") as b:
        with user(_home_user(f"/mnt/{a}", username="covsshmv", home_create=True)) as u:
            old_home = call("user.get_instance", u["id"])["home"]
            ssh(f"rm -rf {old_home}")

            # the move dispatches update_sshpubkey against the missing old home,
            # which must short-circuit instead of raising
            call("user.update", u["id"], {"home": f"/mnt/{b}", "home_create": True})
            assert call("user.get_instance", u["id"])["home"] == f"/mnt/{b}/covsshmv"


# ---------------------------------------------------------------------------
# update_sshpubkey tolerates a group name that can't be resolved to a gid
# ---------------------------------------------------------------------------
def test_sshpubkey_gid_lookup_failure_tolerated():
    with dataset("cov_gidfail") as ds:
        with user(
            _home_user(
                f"/mnt/{ds}",
                username="covgidf",
                home_create=True,
                sshpubkey="ssh-rsa AAAAkey1",
            )
        ) as u:
            grp_id = call("user.get_instance", u["id"])["group"]["id"]
            # Desync the DB group name from /etc/group (datastore only, no reload)
            # so group.get_group_obj raises inside update_sshpubkey; the key write
            # must still succeed with the gid left unchanged.
            call("datastore.update", "account.bsdgroups", grp_id, {"bsdgrp_group": "cov_bogus_grpname"})

            call("user.update", u["id"], {"sshpubkey": "ssh-rsa AAAAkey2"})
            home = call("user.get_instance", u["id"])["home"]
            assert ssh(f"cat {home}/.ssh/authorized_keys").strip() == "ssh-rsa AAAAkey2"
