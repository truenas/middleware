import contextlib

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def user(data):
    user = call("user.create", data)

    try:
        yield call("user.get_instance", user)
    finally:
        call("user.delete", user)


@contextlib.contextmanager
def group(data):
    group = call("group.create", data)

    try:
        yield call("group.get_instance", group)
    finally:
        call("group.delete", group)
