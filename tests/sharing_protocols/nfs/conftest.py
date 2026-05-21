"""Shared fixtures for NFS sharing-protocol tests.

Two helpers here:

* ``start_nfs`` - **session-scoped** fixture that starts nfsd and
  flips ``nfs.config.allow_nonroot=True`` for the entire pytest
  session, then restores the previous setting and stops nfsd at
  session end.  Session scope is required: a per-module
  start/stop cycle causes the appliance-side auth subsystem to
  return ``AUTH_BADCRED`` on the first ``EXCHANGE_ID`` issued in
  each subsequent module.

* ``nfs_dataset`` - context-manager factory that wraps
  ``pool.dataset.create``/``delete`` with sleep+retry on the delete.
  ``sharing.nfs.delete`` removes the export but the kernel takes a
  brief moment to release the underlying ZFS mountpoint; the eager
  ``pool.dataset.delete`` from the standard ``dataset`` asset races
  that and returns ``EZFS_BUSY``.  Same pattern as
  ``tests/api2/test_300_nfs.py:nfs_dataset``.
"""

import contextlib
from time import sleep

import pytest

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.assets.nfs import nfs_server
from middlewared.test.integration.utils import call, pool


@pytest.fixture(scope="session")
def start_nfs():
    """Session-scoped fixture: start nfsd once, flip
    ``allow_nonroot=True`` once, hold across all NFS test modules,
    restore on session teardown.

    ``allow_nonroot`` writes ``insecure`` into the export options;
    without it, Linux nfsd enforces source-port-must-be-privileged
    and rejects pynfs's ephemeral-port operations with
    ``NFS4ERR_PERM`` (test_300_nfs.py::test_share_maproot documents
    this behavior).
    """
    with nfs_server():
        prev_allow_nonroot = call("nfs.config")["allow_nonroot"]
        if not prev_allow_nonroot:
            call("nfs.update", {"allow_nonroot": True})
        try:
            yield
        finally:
            if not prev_allow_nonroot:
                call("nfs.update", {"allow_nonroot": False})


@contextlib.contextmanager
def _nfs_dataset_cm(name, data=None):
    full = f"{pool}/{name}"
    call("pool.dataset.create", {"name": full, **(data or {})})
    try:
        yield full
    finally:
        deleted = False
        # First attempt - may race with NFS export teardown.
        try:
            call("pool.dataset.delete", full, {"recursive": True})
            deleted = True
        except InstanceNotFound:
            deleted = True
        except Exception:
            pass

        # Retry: sleep briefly to let the kernel release the export,
        # then poll until delete succeeds or the dataset is gone.
        if not deleted:
            sleep(2)
            for _ in range(6):
                try:
                    call("pool.dataset.delete", full, {"recursive": True})
                    break
                except InstanceNotFound:
                    break
                except Exception:
                    sleep(10)


@pytest.fixture
def nfs_dataset():
    """Yield a context-manager factory for NFS-test datasets with
    EZFS_BUSY-tolerant cleanup."""
    return _nfs_dataset_cm
