import contextlib

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call


@contextlib.contextmanager
def privilege(data):
    # `privilege.create` grants only the built-in group roles, so a privilege that grants an
    # individual role can only be seeded in the datastore.
    privilege = call("privilege.get_instance", call("datastore.insert", "account.privilege", {
        "local_groups": [],
        "ds_groups": [],
        "roles": [],
        "web_shell": False,
    } | data))

    try:
        yield privilege
    finally:
        try:
            call("privilege.delete", privilege["id"])
        except InstanceNotFound:
            pass



@contextlib.contextmanager
def raw_privilege(data):
    """Insert a privilege row directly into the datastore, ignoring the validation.
    """
    id_ = call("datastore.insert", "account.privilege", {
        "builtin_name": None,
        "name": "Test raw",
        "local_groups": [],
        "ds_groups": [],
        "roles": [],
        "web_shell": False,
        **data,
    })
    try:
        yield id_
    finally:
        call("datastore.delete", "account.privilege", id_)
