import os
import time

import pytest

from contextlib import contextmanager
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

from protocols import smb_connection

SHAREUSER = 'smbuser420'
PASSWD = 'abcd1234'
SMB_NAME = 'tm_share'

# Tests that wait on the deferred-snapshot tevent timer use this value via
# smb_options. Keep it short to keep the test suite quick; the production
# default is 60 seconds.
TM_DEFERRED_SECONDS = 2

# Slack we add when sleeping past the deferred timer so the tevent loop has
# a clear window to dispatch the callback.
TM_TIMER_SLACK = 2

INIT_HISTORY = """ <?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>Snapshots</key>
        <array>
                <dict>
                        <key>com.apple.backupd.SnapshotCompletionDate</key>
                        <date>2025-11-07T21:14:53Z</date>
                        <key>com.apple.backupd.SnapshotName</key>
                        <string>2025-11-07-151453.backup</string>
                </dict>
        </array>
</dict>
</plist> """

FINAL_HISTORY = """ <?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>Snapshots</key>
        <array>
                <dict>
                        <key>com.apple.backupd.SnapshotCompletionDate</key>
                        <date>2025-11-07T21:14:53Z</date>
                        <key>com.apple.backupd.SnapshotName</key>
                        <string>2025-11-07-151453.backup</string>
                </dict>
                <dict>
                        <key>com.apple.backupd.SnapshotCompletionDate</key>
                        <date>2025-11-10T20:19:05Z</date>
                        <key>com.apple.backupd.SnapshotName</key>
                        <string>2025-11-10-141905.backup</string>
                </dict>
        </array>
</dict>
</plist> """

TM = 'ixmini.sparsebundle'
HISTORY_FILE = 'com.apple.TimeMachine.SnapshotHistory.plist'
HISTORY_PATH = os.path.join(TM, HISTORY_FILE)

@pytest.fixture(scope='module')
def aapl_extensions():
    call('smb.update', {'aapl_extensions': True})
    try:
        yield
    finally:
        call('smb.update', {'aapl_extensions': False})


@pytest.fixture(scope='module')
def smb_setup(aapl_extensions):
    with dataset('smb-tm', data={'share_type': 'SMB'}) as ds:
        tm_path = os.path.join('/mnt', ds, TM)
        plist_path = os.path.join(tm_path, HISTORY_FILE)
        ssh(f'mkdir -p {tm_path}')
        ssh(f"echo -n '{INIT_HISTORY}' > {plist_path}")
        with user({
            'username': SHAREUSER,
            'full_name': SHAREUSER,
            'group_create': True,
            'password': PASSWD
        }):
            ssh(f'chown {SHAREUSER} {plist_path}')
            with smb_share(os.path.join('/mnt', ds), SMB_NAME, {
                'purpose': 'TIMEMACHINE_SHARE',
                'options': {'auto_snapshot': True}
            }) as s:
                # Shorten the deferred-snapshot timer so the rename-triggered
                # tests don't wait the production 60s default. The parameter
                # is read per-share by vfs_tmprotect via lp_parm_int(), and
                # setting it in the global section via smb_options propagates
                # to every share that doesn't override it.
                prior_smb_options = call('smb.config')['smb_options']
                call('smb.update', {
                    'smb_options': f'tmprotect:deferred_seconds = {TM_DEFERRED_SECONDS}'
                })
                try:
                    call('service.control', 'START', 'cifs', job=True)
                    yield {
                        'dataset': ds,
                        'share': s,
                        'tm_path': tm_path,
                        'plist_path': plist_path,
                    }
                finally:
                    call('service.control', 'STOP', 'cifs', job=True)
                    call('smb.update', {'smb_options': prior_smb_options})


def check_snapshot_count(dataset_name, expected_count):
    cnt = call('zfs.resource.snapshot.count', {'paths': [dataset_name]}).get(dataset_name, 0)
    assert cnt == expected_count


def write_plist(plist_path, contents=None):
    """Overwrite the SnapshotHistory.plist on disk via SSH (bypasses SMB)."""
    if contents is None:
        contents = INIT_HISTORY
    ssh(f"echo -n '{contents}' > {plist_path}")
    ssh(f'chown {SHAREUSER} {plist_path}')


def delete_aapltm_snapshots(dataset_name):
    """Remove every aapltm-* snapshot on the dataset so subsequent tests start
    from a clean slate (no rate-limit lingering from prior runs)."""
    snaps = call('pool.snapshot.query', [['dataset', '=', dataset_name]])
    for s in snaps:
        if s['snapshot_name'].startswith('aapltm-'):
            call('pool.snapshot.delete', s['id'])


def rename_replace(c, src, dst):
    """SMB rename that overwrites an existing destination, mirroring the
    atomic-rename pattern Time Machine uses to commit a new plist."""
    return c._connection.rename(src, dst, replace=True)


@pytest.fixture
def fresh_tm_state(smb_setup):
    """Reset the on-disk plist to INIT_HISTORY and purge prior aapltm-*
    snapshots before each test that exercises the rename-based path."""
    delete_aapltm_snapshots(smb_setup['dataset'])
    write_plist(smb_setup['plist_path'], INIT_HISTORY)
    check_snapshot_count(smb_setup['dataset'], 0)
    yield
    delete_aapltm_snapshots(smb_setup['dataset'])


def test__do_nothing_no_snapshot(smb_setup):
    """ simple share connect, listdir, disconnect. No snapshot created """
    check_snapshot_count(smb_setup['dataset'], 0)

    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
    ) as c:
        c.ls('/')

    check_snapshot_count(smb_setup['dataset'], 0)


def test__read_plist_no_snapshot(smb_setup):
    """ connect and read our plist, then disconnect without changing it. No snapshot created """
    check_snapshot_count(smb_setup['dataset'], 0)

    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
    ) as c:
        fh = c.create_file(HISTORY_PATH, 'w')
        # arbitrary read of file
        data = c.read(fh, 0, 10)

    check_snapshot_count(smb_setup['dataset'], 0)


def test__write_new_entry_snapshot(smb_setup):
    """ write file that adds to snapshot list """
    check_snapshot_count(smb_setup['dataset'], 0)

    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
    ) as c:
        fh = c.create_file(HISTORY_PATH, 'w')
        data = FINAL_HISTORY.encode()
        c.write(fh, data, len(data))

    check_snapshot_count(smb_setup['dataset'], 1)


# ---------------------------------------------------------------------------
# Rename-triggered (deferred) snapshot tests
#
# vfs_tmprotect installs a SMB_VFS_RENAMEAT hook that schedules a snapshot
# `tmprotect:deferred_seconds` after the most recent rename targeting
# *SnapshotHistory.plist. Time Machine commits its history file via atomic
# rename, and recent macOS builds (a) issue a thundering herd of renames on
# completion and (b) may not promptly disconnect the SMB tree afterwards.
# These tests exercise:
#
#   1. The timer fires while the client is still connected (the bug fix).
#   2. Disconnect within the debounce window takes the snapshot inline and
#      cancels the timer so we never double-snap.
#   3. A burst of renames debounces to exactly one snapshot.
#   4. Renames that don't touch the plist (or don't increase its entry count)
#      do not generate snapshots.
# ---------------------------------------------------------------------------


def _smb_open_plist(c):
    """Open + close the plist for read so vfs_tmprotect's openat hook
    caches its absolute path (config->history_file) and seeds last_count."""
    fh = c.create_file(HISTORY_PATH, 'r')
    try:
        c.read(fh, 0, 1)
    finally:
        c.close(fh)


def _smb_atomic_replace(c, contents, tmp_suffix='.new'):
    """Write `contents` to a sibling temp file and rename it over the plist —
    mirrors the atomic-write pattern Time Machine uses to commit a new plist."""
    tmp = os.path.join(TM, HISTORY_FILE + tmp_suffix)
    fh = c.create_file(tmp, 'w')
    try:
        c.write(fh, contents.encode(), 0)
    finally:
        c.close(fh)
    rename_replace(c, tmp, HISTORY_PATH)


def test__rename_into_plist_disconnect_takes_snapshot_inline(smb_setup, fresh_tm_state):
    """Rename plist → disconnect inside the debounce window. The disconnect
    handler should see config->pending_snap != NULL, cancel the timer, and
    take the snapshot inline before the connection tears down."""
    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
    ) as c:
        _smb_open_plist(c)
        _smb_atomic_replace(c, FINAL_HISTORY)
        # Disconnect immediately — no sleep — so the tevent timer has not had
        # a chance to fire. Disconnect must take the snapshot inline.

    check_snapshot_count(smb_setup['dataset'], 1)


def test__rename_into_plist_timer_fires_while_connected(smb_setup, fresh_tm_state):
    """The headline bug fix: when the client doesn't disconnect after a
    backup, the deferred timer must still fire and create the snapshot."""
    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
    ) as c:
        _smb_open_plist(c)
        _smb_atomic_replace(c, FINAL_HISTORY)

        # Wait for the tevent timer in smbd to fire while we hold the tree.
        time.sleep(TM_DEFERRED_SECONDS + TM_TIMER_SLACK)

        # Snapshot must be present *before* we disconnect.
        check_snapshot_count(smb_setup['dataset'], 1)

    # No double-snap: the rename hook updated last_success when arming the
    # timer, so the disconnect-time history_changed() fallback is a no-op.
    check_snapshot_count(smb_setup['dataset'], 1)


def test__thundering_herd_renames_yield_one_snapshot(smb_setup, fresh_tm_state):
    """macOS has been observed issuing up to ~6 renames in quick succession
    against the same plist at the tail of a backup. Each rename should reset
    the debounce timer; only the final settle produces a snapshot."""
    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
    ) as c:
        _smb_open_plist(c)

        # Six rapid renames into the plist target. After the first one the
        # count has already advanced (INIT→FINAL); renames 2-6 see no further
        # change but still rearm the timer because pending_snap is non-NULL.
        for i in range(6):
            _smb_atomic_replace(c, FINAL_HISTORY, tmp_suffix=f'.herd{i}')

        time.sleep(TM_DEFERRED_SECONDS + TM_TIMER_SLACK)

        check_snapshot_count(smb_setup['dataset'], 1)

    check_snapshot_count(smb_setup['dataset'], 1)


def test__rename_of_unrelated_file_no_snapshot(smb_setup, fresh_tm_state):
    """Renames that don't target *SnapshotHistory.plist must not arm the
    deferred timer."""
    src = os.path.join(TM, 'unrelated_source.dat')
    dst = os.path.join(TM, 'unrelated_destination.dat')

    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
    ) as c:
        _smb_open_plist(c)

        fh = c.create_file(src, 'w')
        try:
            c.write(fh, b'irrelevant', 0)
        finally:
            c.close(fh)
        c.rename(src, dst)

        time.sleep(TM_DEFERRED_SECONDS + TM_TIMER_SLACK)

        check_snapshot_count(smb_setup['dataset'], 0)

    check_snapshot_count(smb_setup['dataset'], 0)


def test__rename_of_plist_with_no_count_change_no_snapshot(smb_setup, fresh_tm_state):
    """A rename whose post-rename plist content has the same entry count and
    same newest timestamp must not arm a timer (and the disconnect-time
    fallback path must also be a no-op)."""
    # Seed the on-disk plist to FINAL_HISTORY so the first openat records
    # last_count=2 / last_success=T2. Any subsequent rename of identical
    # content provides no new evidence of a backup.
    write_plist(smb_setup['plist_path'], FINAL_HISTORY)

    with smb_connection(
        share=smb_setup['share']['name'],
        username=SHAREUSER,
        password=PASSWD,
    ) as c:
        _smb_open_plist(c)
        _smb_atomic_replace(c, FINAL_HISTORY)

        time.sleep(TM_DEFERRED_SECONDS + TM_TIMER_SLACK)

        check_snapshot_count(smb_setup['dataset'], 0)

    check_snapshot_count(smb_setup['dataset'], 0)
