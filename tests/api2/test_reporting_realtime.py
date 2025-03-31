import time

from middlewared.test.integration.assets.account import unprivileged_user_client


def test_reporting_realtime():
    with unprivileged_user_client(["REPORTING_READ"]) as c:
        events = []

        def callback(type, **message):
            events.append((type, message))

        c.subscribe("reporting.realtime", callback, sync=True)

        time.sleep(5)

        assert events
