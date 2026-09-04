import pytest

from middlewared.test.integration.assets.account import user as create_user
from middlewared.test.integration.utils import call


def test_authenticate_root():
    """auth.authenticate_root always returns the full-privilege root credential."""
    cred = call("auth.authenticate_root")
    assert cred["username"] == "root"
    assert "LOCAL" in cred["account_attributes"]
    assert "SYS_ADMIN" in cred["account_attributes"]
    assert cred["privilege"]["webui_access"]


def test_authenticate_user_unknown_username():
    """A username with no matching account row is denied (MatchNotFound branch)."""
    result = call(
        "auth.authenticate_user",
        {
            "pw_name": "this_user_does_not_exist_zzz",
            "pw_uid": 999999,
            "local": True,
            "grouplist": [],
            "account_attributes": [],
            "source": "LOCAL",
        },
    )
    assert result is None


def test_authenticate_user_uid_mismatch():
    """A uid that disagrees with the configuration row is denied."""
    result = call(
        "auth.authenticate_user",
        {
            "pw_name": "root",
            "pw_uid": 999999,  # real root is uid 0
            "local": True,
            "grouplist": [0],
            "account_attributes": [],
            "source": "LOCAL",
        },
    )
    assert result is None


def test_authenticate_user_local_mismatch():
    """A source disagreement (local vs directory) for a matching uid is denied."""
    result = call(
        "auth.authenticate_user",
        {
            "pw_name": "root",
            "pw_uid": 0,
            "local": False,  # root is a local account
            "grouplist": [0],
            "account_attributes": [],
            "source": "ACTIVEDIRECTORY",
        },
    )
    assert result is None


def test_authenticate_user_no_privileges():
    """A valid local user whose groups grant no privilege gets no middleware credential."""
    with create_user(
        {
            "username": "noprivuser",
            "full_name": "noprivuser",
            "group_create": True,
            "password": "test1234",
        }
    ):
        user_obj = call("user.get_user_obj", {"username": "noprivuser", "get_groups": True})
        result = call(
            "auth.authenticate_user",
            {
                "pw_name": user_obj["pw_name"],
                "pw_uid": user_obj["pw_uid"],
                "local": True,
                "grouplist": list(user_obj["grouplist"]),
                "account_attributes": ["LOCAL"],
                "source": "LOCAL",
            },
        )
        assert result is None
