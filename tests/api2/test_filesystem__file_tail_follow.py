import time

import pytest

from middlewared.test.integration.utils import client, ssh


@pytest.mark.flaky(reruns=5, reruns_delay=5)
def test_filesystem__file_tail_follow__grouping():
    ssh("echo > /tmp/file_tail_follow.txt")

    with client() as c:
        received = []

        def append(type, **kwargs):
            received.append((time.monotonic(), kwargs["fields"]["data"]))

        sub_id = c.subscribe('filesystem.file_tail_follow:{"path": "/tmp/file_tail_follow.txt"}', append)

        ssh("for i in `seq 1 200`; do echo test >> /tmp/file_tail_follow.txt; sleep 0.01; done")

        # Settle down things
        time.sleep(1)

        received = received[1:]  # Initial file contents
        # We were sending this for 2-3 seconds, so we should have received 4-6 blocks with 0.5 sec interval
        assert 4 <= len(received) <= 6, str(received)
        # All blocks should have been received uniformly in time
        assert all(0.4 <= b2[0] - b1[0] <= 1.0 for b1, b2 in zip(received[:-1], received[1:])), str(received)
        # All blocks should contain more or less same amount of data: (0.5s grouping / 0.01s interval) <= 60
        assert all(len(block[1].split("\n")) <= 60 for block in received[:-1]), str(received)

        # One single send
        ssh("echo finish >> /tmp/file_tail_follow.txt")

        time.sleep(1)
        assert received[-1][1] == "finish\n"

        # Make sure we can cleanly end the subscription
        c.unsubscribe(sub_id)


def test_filesystem__file_tail_follow__shared_instance_initial_tail():
    ssh("seq 1 10 > /tmp/file_tail_follow2.txt")

    name = 'filesystem.file_tail_follow:{"path": "/tmp/file_tail_follow2.txt", "tail_lines": 5}'
    with client() as c1, client() as c2:
        received1 = []
        received2 = []

        c1.subscribe(name, lambda type, **kwargs: received1.append(kwargs["fields"]["data"]))
        time.sleep(2)
        assert received1 and received1[0] == "6\n7\n8\n9\n10\n", str(received1)

        # An identical subscription re-uses the already running event source instance but must still
        # receive the initial tail
        sub_id2 = c2.subscribe(name, lambda type, **kwargs: received2.append(kwargs["fields"]["data"]))
        time.sleep(2)
        assert received2 and received2[0] == "6\n7\n8\n9\n10\n", str(received2)

        # Both subscribers receive newly appended data
        ssh("echo 11 >> /tmp/file_tail_follow2.txt")
        time.sleep(2)
        assert received1[-1] == "11\n", str(received1)
        assert received2[-1] == "11\n", str(received2)

        # Removing one subscriber must not affect the other one
        c2.unsubscribe(sub_id2)
        ssh("echo 12 >> /tmp/file_tail_follow2.txt")
        time.sleep(2)
        assert received1[-1] == "12\n", str(received1)
        assert received2[-1] == "11\n", str(received2)

        # A client that connects later receives the tail with the lines appended in the meantime
        with client() as c3:
            received3 = []
            c3.subscribe(name, lambda type, **kwargs: received3.append(kwargs["fields"]["data"]))
            time.sleep(2)
            assert received3 and received3[0] == "8\n9\n10\n11\n12\n", str(received3)
