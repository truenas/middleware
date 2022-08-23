import contextlib

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call


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
