import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call


@pytest.fixture(scope="module")
def webshare_group_id():
    """Get the webshare group ID"""
    group = call(
        "group.query",
        [["name", "=", "truenas_webshare"]],
        {"get": True}
    )
    return group["id"]


def test_create_user_with_webshare_enabled(webshare_group_id):
    """Test creating a user with webshare=True adds them to webshare group"""
    with user({
        "username": "webshare_user1",
        "full_name": "Webshare User 1",
        "group_create": True,
        "password": "test1234",
        "webshare": True,
    }) as u:
        # Verify user was created
        assert u["webshare"] is True

        # Verify user is in webshare group
        user_data = call("user.get_instance", u["id"])
        assert webshare_group_id in user_data["groups"], \
            f"User should be in webshare group (id={webshare_group_id})"


def test_create_user_without_webshare(webshare_group_id):
    """Test creating a user without webshare option does not add them to webshare group"""
    with user({
        "username": "webshare_user2",
        "full_name": "Webshare User 2",
        "group_create": True,
        "password": "test1234",
    }) as u:
        # Verify user was created
        assert u["webshare"] is False

        # Verify user is NOT in webshare group
        user_data = call("user.get_instance", u["id"])
        assert webshare_group_id not in user_data["groups"], \
            f"User should not be in webshare group (id={webshare_group_id})"


def test_create_user_with_webshare_disabled(webshare_group_id):
    """Test creating a user with webshare=False does not add them to webshare group"""
    with user({
        "username": "webshare_user3",
        "full_name": "Webshare User 3",
        "group_create": True,
        "password": "test1234",
        "webshare": False,
    }) as u:
        # Verify user was created
        assert u["webshare"] is False

        # Verify user is NOT in webshare group
        user_data = call("user.get_instance", u["id"])
        assert webshare_group_id not in user_data["groups"], \
            f"User should not be in webshare group (id={webshare_group_id})"


def test_update_user_enable_webshare(webshare_group_id):
    """Test updating a user to enable webshare adds them to webshare group"""
    with user({
        "username": "webshare_user4",
        "full_name": "Webshare User 4",
        "group_create": True,
        "password": "test1234",
        "webshare": False,
    }) as u:
        # Verify user starts without webshare
        assert u["webshare"] is False
        user_data = call("user.get_instance", u["id"])
        assert webshare_group_id not in user_data["groups"]

        # Update user to enable webshare
        updated_user = call("user.update", u["id"], {"webshare": True})
        assert updated_user["webshare"] is True

        # Verify user is now in webshare group
        user_data = call("user.get_instance", u["id"])
        assert webshare_group_id in user_data["groups"], \
            f"User should be in webshare group after enabling (id={webshare_group_id})"


def test_update_user_disable_webshare(webshare_group_id):
    """Test updating a user to disable webshare removes them from webshare group"""
    with user({
        "username": "webshare_user5",
        "full_name": "Webshare User 5",
        "group_create": True,
        "password": "test1234",
        "webshare": True,
    }) as u:
        # Verify user starts with webshare enabled
        assert u["webshare"] is True
        user_data = call("user.get_instance", u["id"])
        assert webshare_group_id in user_data["groups"]

        # Update user to disable webshare
        updated_user = call("user.update", u["id"], {"webshare": False})
        assert updated_user["webshare"] is False

        # Verify user is no longer in webshare group
        user_data = call("user.get_instance", u["id"])
        assert webshare_group_id not in user_data["groups"], \
            f"User should not be in webshare group after disabling (id={webshare_group_id})"
