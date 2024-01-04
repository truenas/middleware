# -*- coding=utf-8 -*-
import contextlib
import pprint
import time

from middlewared.test.integration.utils import client


@contextlib.contextmanager
def expect_audit_log(entries, *, include_logins=False):
    with client() as c:
        time.sleep(5)  # FIXME: proper audit log flush

        existing = c.call("audit.query", {"services": ["MIDDLEWARE"]})

        yield

        time.sleep(5)

        new = c.call("audit.query", {"services": ["MIDDLEWARE"]})

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
