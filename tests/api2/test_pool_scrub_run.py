import pprint

import time

import pytest

from auto_config import pool_name
from middlewared.test.integration.utils import client


def test_pool_scrub_alerts():
    with client() as c:
        events = []

        def callback(type, **message):
            events.append((type, message))

        c.subscribe("alert.list", callback, sync=True)

        c.call("pool.scrub.run", pool_name, 0)

        for i in range(10):
            if len(events) != 2:
                time.sleep(1)
                continue

            assert events[0][0] == "ADDED"
            assert events[0][1]["collection"] == "alert.list"
            assert events[0][1]["fields"]["klass"] == "ScrubStarted"
            assert events[1][0] == "REMOVED"
            assert events[1][1]["collection"] == "alert.list"
            assert events[1][1]["id"] == events[0][1]["id"]
            return

        assert False, pprint.pformat(events, indent=2)
