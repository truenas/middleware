import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call


def test_options_may_only_be_changed_by_a_full_admin():
    """`options` lands verbatim in sshd_config, so SSH_WRITE alone may not touch it (NAS-142160)."""
    with unprivileged_user_client(["SSH_WRITE"]) as c:
        with pytest.raises(ValidationErrors) as ve:
            c.call("ssh.update", {"options": "PermitRootLogin yes"})

    assert any(error.attribute == "data.options" for error in ve.value.errors), ve.value.errors


def test_password_login_groups_are_quoted_into_sshd_config():
    """A line break or a double quote in a group name would let SSH_WRITE add the directives `options` denies."""
    with pytest.raises(ValidationErrors) as ve:
        call("ssh.update", {"password_login_groups": ["wheel\nMatch all", 'wheel" User "root']})

    assert {error.attribute for error in ve.value.errors} == {
        "data.password_login_groups.0",
        "data.password_login_groups.1",
    }
