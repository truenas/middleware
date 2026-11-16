# Why SSH: the tests search through SMB with mdsearch, which runs on the system. The API also has no call to make
# test files with Finder tags, to stop one daemon, to read the daemon PIDs, the index directory or the daemon
# configuration file, or to read the datasets under .system.
import base64
import contextlib
import errno
import os
import time

import pytest

from middlewared.service_exception import CallError, ValidationError, ValidationErrors
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, host, mock, ssh

USERNAME = 'alex'
PASSWORD = 'password'
SHARE_NAME = 'alex'
PASSPHRASE = 'truesearch-passphrase'


@pytest.fixture(scope='module')
def make_available():
    # truesearchd and truesearch-indexer each ask middleware for the entitlement when they start.
    with mock('truesearch.unavailable_reasons', return_value=[]):
        with entitled('TRUESEARCH'):
            yield


@pytest.fixture(scope='module')
def share(make_available):
    protocols = call('smb.config')['search_protocols']
    call('smb.update', {'search_protocols': ['SPOTLIGHT']})
    try:
        with dataset('truesearch', data={'share_type': 'SMB'}) as ds:
            ssh(f"touch /mnt/{ds}/mytest.txt")

            with user({
                'username': USERNAME,
                'full_name': 'Alex',
                'group_create': True,
                'password': PASSWORD
            }):
                with smb_share(os.path.join('/mnt', ds), SHARE_NAME) as smb:
                    yield {
                        'dataset': ds,
                        'share': smb,
                    }
    finally:
        call('smb.update', {'search_protocols': protocols})


@contextlib.contextmanager
def another_share(path: str, name: str, **options):
    # smb_share stops the SMB service when it exits. The tests that follow need the service.
    share_id = call('sharing.smb.create', {'path': path, 'name': name, **options})['id']
    try:
        yield
    finally:
        call('sharing.smb.delete', share_id)


def expect_search_result(expected: list[str]):
    # This search goes through SMB, as a search from a Mac does. mdsearch is the Spotlight client of Samba, so the
    # query uses the Spotlight syntax. truesearch.query does not use this syntax.
    for i in range(10):
        result = ssh(f"mdsearch --debug-stdout -U {USERNAME} --password={PASSWORD} {host().ip} {SHARE_NAME} "
                     "'kMDItemDisplayName==\"*test*\"'", check=False, complete_response=True)
        if sorted(result["stdout"].splitlines()) == sorted(expected):
            break

        time.sleep(5)
    else:
        assert False, (result["returncode"], result["output"])


def query(path: str, filters: list, **fields):
    return call('truesearch.query', {
        'path': path, 'query-filters': filters, 'query-options': {'limit': 100}, **fields,
    })


def expect_api_query(path: str, filters: list, expected: list[str], **fields):
    for i in range(10):
        try:
            result = query(path, filters, **fields)
        except Exception as e:
            # The index target of a dataset mounted a moment ago is not served yet.
            result = e
        else:
            if sorted(entry['path'] for entry in result) == sorted(expected):
                return result

        time.sleep(5)

    assert False, result


def test_index_and_search(share):
    expect_search_result(["mytest.txt"])


def test_query_api(share):
    hits = expect_api_query(f"/mnt/{share['dataset']}", [['name', 'Crin', 'MYTEST']],
                            [f"/mnt/{share['dataset']}/mytest.txt"])
    assert hits[0]['name'] == 'mytest.txt'
    assert hits[0]['inode'] == int(ssh(f"stat -c %i /mnt/{share['dataset']}/mytest.txt"))
    # The handle is the one that the kernel gives the file.
    path = f"/mnt/{share['dataset']}/mytest.txt"
    kernel = ssh(f"python3 -c \"import truenas_os; print(bytes(truenas_os.fhandle(path='{path}')).hex())\"").strip()
    assert base64.b64decode(hits[0]['handle']).hex() == kernel
    assert hits[0]['type'] == 'FILE'
    assert hits[0]['size'] == 0


def expect_status(ds: str):
    for i in range(10):
        status = call('truesearch.status')
        entry = next((d for d in status['datasets'] if d['dataset'] == ds), None)
        if entry is not None and entry['state'] == 'READY' and entry['served']:
            return status, entry

        time.sleep(5)

    assert False, status


def daemon_pids() -> list[str]:
    return ssh("systemctl show -p MainPID --value truesearchd truesearch-indexer").split()


def environments() -> set[str]:
    return set(ssh("ls /var/db/system/truesearchd").split())


def configuration_rows() -> dict[str, dict[str, str]]:
    # The settings of each row of the configuration file, by dataset. A row is a comment that names its dataset, a
    # header, then the settings. truesearch_client does not read the exclusions of a row, so the test reads the file.
    rows = {}
    for row in ssh('cat /etc/truesearchd/truesearch.conf').split('\n\n')[1:]:
        comment, _header, *settings = row.splitlines()
        rows[comment.removeprefix('# ')] = dict(setting.split(' = ', 1) for setting in settings)
    return rows


def test_status(share):
    status, entry = expect_status(share['dataset'])
    assert status['running'] is True
    assert entry['path'] == f"/mnt/{share['dataset']}"
    assert entry['entries'] >= 1
    assert entry['last_full_pass'] is not None


def test_a_daemon_that_runs_alone_restarts_with_the_other(share):
    expect_status(share['dataset'])
    ssh('systemctl stop truesearch-indexer')
    # The service is stopped, because one daemon is down. truesearchd still runs, and it holds the datasets.
    alone, stopped = daemon_pids()
    assert alone != '0'
    assert stopped == '0'

    call('truesearch.configure')
    # truesearchd reads the configuration file only when it starts. So both daemons start again.
    pids = daemon_pids()
    assert '0' not in pids
    assert pids[0] != alone
    expect_search_result(["mytest.txt"])


def test_status_while_both_daemons_are_stopped(share):
    expect_status(share['dataset'])
    ssh('systemctl stop truesearchd truesearch-indexer')
    try:
        status = call('truesearch.status')
        assert (status['running'], status['index_bytes'], status['space_low']) == (False, None, None)
        entry = next(d for d in status['datasets'] if d['dataset'] == share['dataset'])
        assert (entry['state'], entry['served'], entry['entries']) == ('STOPPED', False, None)
    finally:
        call('truesearch.configure')

    expect_status(share['dataset'])


def test_time_machine_and_home_shares_are_not_indexed(share):
    ds = share['dataset']
    aapl_extensions = call('smb.config')['aapl_extensions']
    call('smb.update', {'aapl_extensions': True})
    ssh(f"mkdir /mnt/{ds}/timemachine")
    try:
        with (
            dataset('truesearch/backups', data={'share_type': 'SMB'}) as backups,
            dataset('truesearch_homes', data={'share_type': 'SMB'}) as homes,
            # A disabled Time Machine share keeps its backups. So its directory stays excluded.
            another_share(f"/mnt/{ds}/timemachine", 'truesearch_tm', purpose='TIMEMACHINE_SHARE', enabled=False),
            another_share(f"/mnt/{backups}", 'truesearch_backups', purpose='TIMEMACHINE_SHARE'),
            another_share(f"/mnt/{homes}", 'truesearch_homes', purpose='LEGACY_SHARE', options={'home': True}),
        ):
            call('truesearch.configure')
            rows = configuration_rows()
            assert rows[ds].get('exclude') == '"timemachine"'
            # The dataset of a Time Machine share gets no row, and a home share is not indexed.
            assert backups not in rows
            assert homes not in rows
    finally:
        ssh(f"rm -r /mnt/{ds}/timemachine")
        call('smb.update', {'aapl_extensions': aapl_extensions})


def test_nested_dataset_has_its_own_index(share):
    with dataset('truesearch/nested', data={'share_type': 'SMB'}) as ds:
        ssh(f"touch /mnt/{ds}/anothertest.txt")

        # TrueSearch is reconfigured 1 second after the mount and then needs time to index
        expect_api_query(f"/mnt/{ds}", [['name', '^', 'anothertest']], [f"/mnt/{ds}/anothertest.txt"])

        # A search through a share stays on the share's dataset.
        expect_search_result(["mytest.txt"])

        # A query from the parent dataset finds the file only with recursive.
        parent = f"/mnt/{share['dataset']}"
        assert query(parent, [['name', '^', 'anothertest']]) == []
        expect_api_query(parent, [['name', '^', 'anothertest']], [f"/mnt/{ds}/anothertest.txt"], recursive=True)


def test_destroying_an_indexed_dataset_keeps_the_others_served(share):
    with dataset('truesearch/destroyed', data={'share_type': 'SMB'}) as ds:
        ssh(f"touch /mnt/{ds}/destroyedtest.txt")
        expect_api_query(f"/mnt/{ds}", [['name', '^', 'destroyedtest']], [f"/mnt/{ds}/destroyedtest.txt"])
        pids = daemon_pids()

    # The destroy released that dataset with a reload. Both daemons continued to run and to serve the share.
    assert daemon_pids() == pids
    status, entry = expect_status(share['dataset'])
    assert ds not in [d['dataset'] for d in status['datasets']]
    expect_search_result(["mytest.txt"])


def test_a_disabled_share_keeps_its_index(share):
    with dataset('truesearch_other', data={'share_type': 'SMB'}) as other:
        with another_share(os.path.join('/mnt', other), 'truesearch_other'):
            expect_status(other)
            expect_status(share['dataset'])
            kept, pids = environments(), daemon_pids()
            assert kept

            call('sharing.smb.update', share['share']['id'], {'enabled': False})
            try:
                # TrueSearch continues to run for the other share. The dataset of the disabled share is not
                # indexed, and its index stays.
                assert share['dataset'] not in [d['dataset'] for d in call('truesearch.status')['datasets']]
                assert environments() == kept
                assert daemon_pids() == pids
            finally:
                call('sharing.smb.update', share['share']['id'], {'enabled': True})

            expect_status(share['dataset'])
            expect_search_result(["mytest.txt"])
            assert environments() == kept


def test_export_and_import_keep_the_index(share):
    with another_pool() as pool:
        with dataset('indexed', data={'share_type': 'SMB'}, pool=pool['name']) as ds:
            ssh(f"touch /mnt/{ds}/exportedtest.txt")
            with another_share(os.path.join('/mnt', ds), 'truesearch_export'):
                expect_api_query(f"/mnt/{ds}", [['name', '^', 'exportedtest']], [f"/mnt/{ds}/exportedtest.txt"])
                kept, pids = environments(), daemon_pids()
                assert kept

                # TrueSearch releases the pool with a reload, so the export stops neither daemon.
                call('pool.export', pool['id'], job=True)
                try:
                    assert daemon_pids() == pids
                    assert environments() == kept
                    expect_search_result(["mytest.txt"])
                finally:
                    call('pool.import_pool', {'guid': pool['guid']}, job=True)
                # The import enables the share again. The daemons open the old index and do not build a new one.
                expect_api_query(f"/mnt/{ds}", [['name', '^', 'exportedtest']], [f"/mnt/{ds}/exportedtest.txt"])
                assert environments() == kept


def test_the_index_dataset_is_encrypted_with_the_pwenc_secret(share):
    pool = call('systemdataset.config')['pool']
    properties = ssh(f"zfs get -H -o value encryption,keyformat,keylocation,keystatus {pool}/.system/truesearchd")
    assert properties.split() == ['aes-256-gcm', 'raw', 'file:///data/pwenc_secret', 'available']


def test_an_encrypted_dataset_is_indexed_and_can_be_locked(share):
    with dataset('truesearch/locked', data={
        'share_type': 'SMB',
        'encryption': True,
        'inherit_encryption': False,
        'encryption_options': {'generate_key': False, 'passphrase': PASSPHRASE},
    }) as ds:
        ssh(f"touch /mnt/{ds}/lockedtest.txt")
        expect_api_query(f"/mnt/{ds}", [['name', '^', 'lockedtest']], [f"/mnt/{ds}/lockedtest.txt"])
        kept = environments()
        assert kept

        # Both daemons release the dataset before the lock unmounts it. Its row is disabled, and its index stays.
        call('pool.dataset.lock', ds, job=True)
        try:
            assert ds not in [d['dataset'] for d in call('truesearch.status')['datasets']]
            assert environments() == kept
        finally:
            call('pool.dataset.unlock', ds.split('/')[0], {
                'datasets': [{'name': ds, 'passphrase': PASSPHRASE}], 'recursive': True,
            }, job=True)
        expect_api_query(f"/mnt/{ds}", [['name', '^', 'lockedtest']], [f"/mnt/{ds}/lockedtest.txt"])


def test_a_system_dataset_move_makes_the_index_dataset_again(share):
    pool = call('systemdataset.config')['pool']
    with another_pool() as other:
        call('systemdataset.update', {'pool': other['name']}, job=True)
        try:
            index_dataset = f"{other['name']}/.system/truesearchd"
            properties = ssh(f"zfs get -H -o value encryption,keyformat,keylocation,keystatus {index_dataset}")
            assert properties.split() == ['aes-256-gcm', 'raw', 'file:///data/pwenc_secret', 'available']
            # The indexes are not copied. truesearch-indexer builds them again on the new pool.
            expect_search_result(["mytest.txt"])
        finally:
            call('systemdataset.update', {'pool': pool}, job=True)

    expect_search_result(["mytest.txt"])


def test_user_cannot_read_file(share):
    prohibited_dir = f"/mnt/{share['dataset']}/prohibited"
    ssh(f"mkdir {prohibited_dir}")
    ssh(f"touch {prohibited_dir}/prohibitedtest.txt")

    expect_search_result(["mytest.txt", "prohibited/prohibitedtest.txt"])

    call("filesystem.setperm", {"path": prohibited_dir, "mode": "700", "options": {"stripacl": True}}, job=True)

    expect_search_result(["mytest.txt"])


def test_query_as_a_user(share):
    hidden_dir = f"/mnt/{share['dataset']}/hidden"
    ssh(f"mkdir {hidden_dir}")
    ssh(f"touch {hidden_dir}/hiddentest.txt")
    call("filesystem.setperm", {"path": hidden_dir, "mode": "700", "options": {"stripacl": True}}, job=True)

    # Root sees every match. The user sees what the user can reach.
    expect_api_query(f"/mnt/{share['dataset']}", [['name', '^', 'hiddentest']], [f"{hidden_dir}/hiddentest.txt"])
    assert query(f"/mnt/{share['dataset']}", [['name', '^', 'hiddentest']], username=USERNAME) == []


def test_query_filters(share):
    base = f"/mnt/{share['dataset']}/filters"
    ssh(f"mkdir -p {base}/docs && truncate -s 3000 {base}/report.pdf && truncate -s 10 {base}/notes.txt && "
        f"ln -s notes.txt {base}/link")
    # A Mac stores Finder tags in a Samba stream: a binary plist and one trailing byte.
    ssh(f"""python3 - <<'EOF'
import os, plistlib
os.setxattr({base + '/notes.txt'!r}, 'user.DosStream.com.apple.metadata\\uf022_kMDItemUserTags:$DATA',
            plistlib.dumps(['Red\\n6'], fmt=plistlib.FMT_BINARY) + b'\\0')
EOF""")

    expect_api_query(base, [['name', 'C^', 'REPORT']], [f"{base}/report.pdf"])
    expect_api_query(base, [['macos_kind', '=', 'PDF']], [f"{base}/report.pdf"])
    expect_api_query(base, [['size', '>', 1000], ['type', '=', 'FILE']], [f"{base}/report.pdf"])
    expect_api_query(base, [['type', '=', 'DIRECTORY']], [f"{base}/docs"])
    expect_api_query(base, [['type', '=', 'SYMLINK']], [f"{base}/link"])
    expect_api_query(base, [['type', '=', 'FILE']], [f"{base}/report.pdf", f"{base}/notes.txt"])
    expect_api_query(base, [['tags', 'Crin', 'red']], [f"{base}/notes.txt"])
    expect_api_query(base, [['OR', [['name', 'Crin', 'OTES'], ['name', '$', '.pdf']]]],
                     [f"{base}/notes.txt", f"{base}/report.pdf"])
    expect_api_query(base, [['mtime.$date', '>', '2000-01-01T00:00:00']],
                     [f"{base}/docs", f"{base}/report.pdf", f"{base}/notes.txt", f"{base}/link"])
    assert len(query(base, [])) == 4
    assert len(query(base, [], **{'query-options': {'limit': 1}})) == 1

    with pytest.raises(ValidationError):
        query(base, [['name', '~', 'rep.*']])
    for option in ({'order_by': ['size']}, {'offset': 1}, {'get': True}, {'select': ['name']}):
        with pytest.raises(ValidationErrors):
            query(base, [], **{'query-options': option})


@pytest.mark.parametrize('path', [
    '/mnt/tank/data/shares/../etc',
    '/mnt/tank/data//shares',
    '/mnt/./tank',
    'mnt/tank/data',
    '/etc/passwd',
    # Each is /mnt once it is normalized.
    '/mnt/',
    '/mnt//',
])
def test_query_refuses_a_path_outside_mnt_or_with_dot_components(path):
    with pytest.raises(ValidationError):
        query(path, [])


def test_query_of_a_path_that_no_index_holds_is_refused(share):
    with pytest.raises(CallError) as e:
        query(f"/mnt/{share['dataset'].split('/')[0]}", [])
    assert e.value.errno == errno.ENOENT
