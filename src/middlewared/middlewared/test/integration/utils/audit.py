# -*- coding=utf-8 -*-
import contextlib
import pprint
import time

from middlewared.test.integration.utils import client


DEFLIMIT = 10000


@contextlib.contextmanager
def expect_audit_log(entries, *, include_logins=False):
    with client() as c:
        time.sleep(5)  # FIXME: proper audit log flush

        existing = c.call("audit.query", {"services": ["MIDDLEWARE"], "query-options": {"limit": DEFLIMIT}})

        yield

        time.sleep(5)

        new = c.call("audit.query", {"services": ["MIDDLEWARE"], "query-options": {"limit": DEFLIMIT}})

    assert new[:len(existing)] == existing

    new = new[len(existing):]

    if not include_logins:
        new = [entry for entry in new if entry["event"] != "AUTHENTICATION"]

    assert len(new) == len(entries), \
        f"Expected:\n{pprint.pformat(entries, indent=2)}\nGot:\n{pprint.pformat(new, indent=2)}"

    for new_entry, expected_entry in zip(new, entries):
        assert expected_entry.items() < new_entry.items(), \
            f"Expected:\n{pprint.pformat(expected_entry, indent=2)}\nGot:\n{pprint.pformat(new_entry, indent=2)}"


@contextlib.contextmanager
def expect_audit_method_calls(calls):
    with expect_audit_log([
        {
            "event": "METHOD_CALL",
            "event_data": {
                "authenticated": True,
                "authorized": True,
                **call,
            },
        }
        for call in calls
    ]):
        yield


def get_audit_entry(service, index=-1):
    """
    service one of the audited services: 'MIDDLEWARE', 'SMB', 'SUDO' (see plugins/audit/utils.py)
    index is which entry to return.  The default (-1) is the last entry
    """
    svc = str(service).upper()
    assert svc in ['MIDDLEWARE', 'SMB', 'SUDO']
    assert isinstance(index, int)

    entry = {}
    offset = 0
    if index < 0:
        max_count = 0
        with client() as c:
            if 0 < (max_count := c.call("audit.query", {"services": [svc], "query-options": {"count": True}})):
                offset = max_count - 1
    else:
        offset = index

    assert offset > -1
    with client() as c:
        entry_list = c.call('audit.query', {"services": [svc], "query-options": {"offset": offset, "limit": DEFLIMIT}})

    if len(entry_list):
        entry = entry_list[0]

    return entry
