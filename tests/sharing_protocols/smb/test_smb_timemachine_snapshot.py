import os
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
def smb_setup(request):
    with dataset('smb-tm', data={'share_type': 'SMB'}) as ds:
        ssh(f'mkdir -p {os.path.join("/mnt", ds, TM)}')
        ssh(f'echo -n {INIT_HISTORY} > {os.path.join("/mnt", ds, TM, HISTORY_FILE)}')
        with user({
            'username': SHAREUSER,
            'full_name': SHAREUSER,
            'group_create': True,
            'password': PASSWD
        }):
            with smb_share(os.path.join('/mnt', ds), SMB_NAME, {
                'purpose': 'TIMEMACHINE_SHARE',
                'options': {'auto_snapshot': True}
            }) as s:
                try:
                    call('service.control', 'START', 'cifs', job=True)
                    yield {'dataset': ds, 'share': s}
                finally:
                    call('service.control', 'STOP', 'cifs', job=True)


def check_snapshot_count(datset_name, expected_count):
    cnt = call('zfs.snapshot.count')[dataset_name]
    assert cnt == expected_count


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
