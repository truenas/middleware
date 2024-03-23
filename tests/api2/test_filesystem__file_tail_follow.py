import time

import pytest

from middlewared.test.integration.utils import client, ssh

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
pytestmark = pytest.mark.fs


@pytest.mark.flaky(reruns=5, reruns_delay=5)
def test_filesystem__file_tail_follow__grouping():
    ssh("echo > /tmp/file_tail_follow.txt")

    with client() as c:
        received = []

        def append(type, **kwargs):
            received.append((time.monotonic(), kwargs["fields"]["data"]))

        c.subscribe("filesystem.file_tail_follow:/tmp/file_tail_follow.txt", append)

        ssh("for i in `seq 1 200`; do echo test >> /tmp/file_tail_follow.txt; sleep 0.01; done")

        # Settle down things
        time.sleep(1)

        received = received[1:]  # Initial file contents
        # We were sending this for 2-3 seconds so we should have received 4-6 blocks with 0.5 sec interval
        assert 4 <= len(received) <= 6, str(received)
        # All blocks should have been received uniformly in time
        assert all(0.4 <= b2[0] - b1[0] <= 1.0 for b1, b2 in zip(received[:-1], received[1:])), str(received)
        # All blocks should contains more or less same amount of data
        assert all(30 <= len(block[1].split("\n")) <= 60 for block in received[:-1]), str(received)

        # One single send
        ssh("echo finish >> /tmp/file_tail_follow.txt")

        time.sleep(1)
        assert received[-1][1] == "finish\n"
