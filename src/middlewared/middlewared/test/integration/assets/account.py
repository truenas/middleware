import contextlib
import types

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call, ssh


@contextlib.contextmanager
def user(data):
    user = call("user.create", data)

    try:
        yield call("user.get_instance", user)
    finally:
        try:
            call("user.delete", user)
        except InstanceNotFound:
            pass


@contextlib.contextmanager
def group(data):
    group = call("group.create", data)

    try:
        yield call("group.get_instance", group)
    finally:
        try:
            call("group.delete", group)
        except InstanceNotFound:
            pass


@contextlib.contextmanager
def unprivileged_user(*, username, group_name, privilege_name, allowlist, web_shell):
    with group({
        "name": group_name,
    }) as g:
        with privilege({
            "name": privilege_name,
            "local_groups": [g["gid"]],
            "ds_groups": [],
            "allowlist": allowlist,
            "web_shell": web_shell,
        }):
            with dataset(f"{username}_homedir") as homedir:
                if web_shell:
                    # To prevent `zsh-newuser-install` interactive prompt
                    ssh(f"touch /mnt/{homedir}/.zshrc")

                password = "test1234"
                with user({
                    "username": username,
                    "full_name": "Unprivileged user",
                    "group_create": True,
                    "groups": [g["id"]],
                    "home": f"/mnt/{homedir}",
                    "password": password,
                }):
                    yield types.SimpleNamespace(username=username, password=password)
