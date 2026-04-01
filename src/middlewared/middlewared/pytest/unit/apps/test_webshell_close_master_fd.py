import os
import threading

import pytest

from middlewared.apps.webshell_app import ShellWorkerThread


def make_worker(fd):
    """Create a ShellWorkerThread with just enough state to test close_master_fd."""
    worker = object.__new__(ShellWorkerThread)
    worker.master_fd = fd
    return worker


def test_close_master_fd_none():
    """close_master_fd is a no-op when master_fd is already None."""
    worker = make_worker(None)
    worker.close_master_fd()
    assert worker.master_fd is None


def test_close_master_fd_closes_fd():
    """close_master_fd closes the fd and sets master_fd to None."""
    r, w = os.pipe()
    os.close(w)
    worker = make_worker(r)
    worker.close_master_fd()
    assert worker.master_fd is None

    # Verify the fd was actually closed
    with pytest.raises(OSError):
        os.close(r)


def test_close_master_fd_concurrent():
    """Only one of two concurrent callers should actually close the fd."""
    r, w = os.pipe()
    os.close(w)
    worker = make_worker(r)

    barrier = threading.Barrier(2)
    errors = []

    def closer():
        barrier.wait()
        try:
            worker.close_master_fd()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=closer) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert worker.master_fd is None
    assert not errors, f"close_master_fd raised: {errors}"

    # Verify the fd was closed exactly once
    with pytest.raises(OSError):
        os.close(r)
