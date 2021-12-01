import contextlib

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def user(data):
    user = call("user.create", data)

    try:
        yield user
    finally:
        call("user.delete", user)


@contextlib.contextmanager
def group(data):
    group = call("group.create", data)

    try:
        yield group
    finally:
        call("group.delete", group)
