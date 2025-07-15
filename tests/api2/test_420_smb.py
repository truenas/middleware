import pytest
import sys
import os
import secrets
import string
import uuid
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from protocols import smb_connection
from utils import create_dataset
from auto_config import pool_name
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset as make_dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.system import reset_systemd_svcs


AUDIT_WAIT = 10
SMB_NAME = "TestCifsSMB"
SHAREUSER = 'smbuser420'
PASSWD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))


@pytest.fixture(scope='module')
def smb_info():
    with make_dataset('smb-cifs', data={'share_type': 'SMB'}) as ds:
        with user({
            'username': SHAREUSER,
            'full_name': SHAREUSER,
            'group_create': True,
            'password': PASSWD
        }):
            with smb_share(os.path.join('/mnt', ds), SMB_NAME, {
                'purpose': 'LEGACY_SHARE',
            }) as s:
                try:
                    call('smb.update', {
                        'guest': SHAREUSER
                    })
                    call('service.update', 'cifs', {'enable': True})
                    call('service.control', 'START', 'cifs', job=True)
                    yield {'dataset': ds, 'share': s}
                finally:
                    call('smb.update', {
                        'guest': 'nobody'
                    })
                    call('service.control', 'STOP', 'cifs', job=True)
                    call('service.update', 'cifs', {'enable': False})


@pytest.fixture(scope='function')
def enable_guest(smb_info):
    smb_id = smb_info['share']['id']
    call('sharing.smb.update', smb_id, {'purpose': 'LEGACY_SHARE', 'options': {'guestok': True}})
    try:
        yield
    finally:
        call('sharing.smb.update', smb_id, {'purpose': 'LEGACY_SHARE', 'options': {'guestok': False}})


@pytest.fixture(scope='function')
def enable_aapl():
    reset_systemd_svcs('smbd')
    call('smb.update', {'aapl_extensions': True})

    try:
        yield
    finally:
        call('smb.update', {'aapl_extensions': False})


@pytest.fixture(scope='function')
def enable_smb1():
    reset_systemd_svcs('smbd')
    call('smb.update', {'enable_smb1': True})

    try:
        yield
    finally:
        call('smb.update', {'enable_smb1': False})


@pytest.fixture(scope='function')
def enable_recycle_bin(smb_info):
    smb_id = smb_info['share']['id']
    call('sharing.smb.update', smb_id, {'purpose': 'LEGACY_SHARE', 'options': {'recyclebin': True}})

    try:
        yield
    finally:
        call('sharing.smb.update', smb_id, {'purpose': 'LEGACY_SHARE', 'options': {'recyclebin': False}})


@pytest.mark.parametrize('proto,runas', [
    ('SMB1', 'GUEST'),
    ('SMB2', 'GUEST'),
    ('SMB1', SHAREUSER),
    ('SMB2', SHAREUSER)
])
def test__basic_smb_ops(enable_smb1, enable_guest, proto, runas):
    with smb_connection(
        share=SMB_NAME,
        username=runas,
        password=PASSWD,
        smb1=(proto == 'SMB1')
    ) as c:
        filename1 = f'testfile1_{proto.lower()}_{runas}.txt'
        filename2 = f'testfile2_{proto.lower()}_{runas}.txt'
        dirname = f'testdir_{proto.lower()}_{runas}.txt'

        fd = c.create_file(filename1, 'w')
        c.write(fd, b'foo')
        val = c.read(fd, 0, 3)
        c.close(fd, True)
        assert val == b'foo'

        c.mkdir(dirname)
        fd = c.create_file(f'{dirname}/{filename2}', 'w')
        c.write(fd, b'foo2')
        val = c.read(fd, 0, 4)
        c.close(fd, True)
        assert val == b'foo2'

        c.rmdir(dirname)

        # DELETE_ON_CLOSE flag was set prior to closing files
        # and so root directory should be empty
        assert c.ls('/') == []


def test__change_sharing_smd_home_to_true(smb_info):
    reset_systemd_svcs('smbd')
    smb_id = smb_info['share']['id']
    share = call('sharing.smb.update', smb_id, {'purpose': 'LEGACY_SHARE', 'options': {'home': True}})
    try:
        share_path = call('smb.getparm', 'path', 'homes')
        assert share_path == f'{share["path"]}/%U'
    finally:
        new_info = call('sharing.smb.update', smb_id, {'purpose': 'LEGACY_SHARE', 'options': {'home': False}})

    share_path = call('smb.getparm', 'path', new_info['name'])
    assert share_path == share['path']
    obey_pam_restrictions = call('smb.getparm', 'obey pam restrictions', 'GLOBAL')
    assert obey_pam_restrictions is False


def test__change_timemachine_to_true(enable_aapl, smb_info):
    smb_id = smb_info['share']['id']
    call('sharing.smb.update', smb_id, {'purpose': 'TIMEMACHINE_SHARE', 'options': {}})
    try:
        share_info = call('sharing.smb.query', [['id', '=', smb_id]], {'get': True})
        assert share_info['purpose'] == 'TIMEMACHINE_SHARE'

        enabled = call('smb.getparm', 'fruit:time machine', share_info['name'])
        assert enabled == 'True'

        vfs_obj = call('smb.getparm', 'vfs objects', share_info['name'])
        assert 'fruit' in vfs_obj
    finally:
        call('sharing.smb.update', smb_id, {'purpose': 'DEFAULT_SHARE'})


def do_recycle_ops(c, has_subds=False):
    # Our recycle repository should be auto-created on connect.
    fd = c.create_file('testfile.txt', 'w')
    c.write(fd, b'foo')
    c.close(fd, True)

    # Above close op also deleted the file and so
    # we expect file to now exist in the user's .recycle directory
    fd = c.create_file(f'.recycle/{SHAREUSER}/testfile.txt', 'r')
    val = c.read(fd, 0, 3)
    c.close(fd)
    assert val == b'foo'

    # re-open so that we can set DELETE_ON_CLOSE
    # this verifies that SMB client can purge file from recycle bin
    c.close(c.create_file(f'.recycle/{SHAREUSER}/testfile.txt', 'w'), True)
    assert c.ls(f'.recycle/{SHAREUSER}/') == []

    if not has_subds:
        return

    # nested datasets get their own recycle bin to preserve atomicity of
    # rename op.
    fd = c.create_file('subds/testfile2.txt', 'w')
    c.write(fd, b'boo')
    c.close(fd, True)

    fd = c.create_file(f'subds/.recycle/{SHAREUSER}/testfile2.txt', 'r')
    val = c.read(fd, 0, 3)
    c.close(fd)
    assert val == b'boo'

    c.close(c.create_file(f'subds/.recycle/{SHAREUSER}/testfile2.txt', 'w'), True)
    assert c.ls(f'subds/.recycle/{SHAREUSER}/') == []


def test__recyclebin_functional_test(enable_recycle_bin, smb_info):
    with create_dataset(f'{smb_info["dataset"]}/subds', {'share_type': 'SMB'}):
        with smb_connection(
            share=SMB_NAME,
            username=SHAREUSER,
            password=PASSWD,
        ) as c:
            do_recycle_ops(c, True)


@pytest.mark.parametrize('smb_config', [
    {'global': {'aapl_extensions': True}, 'share': {'aapl_name_mangling': True}},
    {'global': {'aapl_extensions': True}, 'share': {'aapl_name_mangling': False}},
    {'global': {'aapl_extensions': False}, 'share': {}},
])
def test__recyclebin_functional_test_subdir(smb_info, smb_config):
    tmp_ds = f"{pool_name}/recycle_test"
    tmp_ds_path = f'/mnt/{tmp_ds}/subdir'
    tmp_share_name = 'recycle_test'

    reset_systemd_svcs('smbd')
    call('smb.update', smb_config['global'])
    # basic tests of recyclebin operations
    with create_dataset(tmp_ds, {'share_type': 'SMB'}):
        ssh(f'mkdir {tmp_ds_path}')
        with smb_share(tmp_ds_path, tmp_share_name, {
            'purpose': 'LEGACY_SHARE',
            'options': {'recyclebin': True} | smb_config['share'],
        }):
            shares = call('sharing.smb.smbconf_list_shares')
            assert tmp_share_name in shares
            with smb_connection(
                share=tmp_share_name,
                username=SHAREUSER,
                password=PASSWD,
            ) as c:
                do_recycle_ops(c)

    # more abusive test where first TCON op is opening file in subdir to delete
    with create_dataset(tmp_ds, {'share_type': 'SMB'}):
        ops = [
            f'mkdir {tmp_ds_path}',
            f'mkdir {tmp_ds_path}/subdir',
            f'touch {tmp_ds_path}/subdir/testfile',
            f'chown {SHAREUSER} {tmp_ds_path}/subdir/testfile',
        ]
        ssh(';'.join(ops))
        with smb_share(tmp_ds_path, tmp_share_name, {
            'purpose': 'LEGACY_SHARE',
            'options': {'recyclebin': True} | smb_config['share'],
        }):
            shares = call('sharing.smb.smbconf_list_shares')
            assert tmp_share_name in shares

            with smb_connection(
                share=tmp_share_name,
                username=SHAREUSER,
                password=PASSWD,
            ) as c:
                fd = c.create_file('subdir/testfile', 'w')
                c.write(fd, b'boo')
                c.close(fd, True)

                fd = c.create_file(f'.recycle/{SHAREUSER}/subdir/testfile', 'r')
                val = c.read(fd, 0, 3)
                c.close(fd)
                assert val == b'boo'


def test__netbios_name_change_check_sid():
    """ changing netbiosname should not alter our local sid value """
    orig = call('smb.config')
    new_sid = call('smb.update', {'netbiosname': 'nb_new'})['server_sid']

    try:
        assert new_sid == orig['server_sid']
        localsid = call('smb.groupmap_list')['localsid']
        assert new_sid == localsid
    finally:
        call('smb.update', {'netbiosname': orig['netbiosname']})


AUDIT_FIELDS = [
    'audit_id', 'timestamp', 'address', 'username', 'session', 'service',
    'service_data', 'event', 'event_data', 'success'
]


def validate_vers(vers, expected_major, expected_minor):
    assert 'major' in vers, str(vers)
    assert 'minor' in vers, str(vers)
    assert vers['major'] == expected_major
    assert vers['minor'] == expected_minor


def validate_svc_data(msg, svc):
    assert 'service_data' in msg, str(msg)
    svc_data = msg['service_data']
    for key in ['vers', 'service', 'session_id', 'tcon_id']:
        assert key in svc_data, str(svc_data)

    assert svc_data['service'] == svc

    assert isinstance(svc_data['session_id'], str)
    assert svc_data['session_id'].isdigit()

    assert isinstance(svc_data['tcon_id'], str)
    assert svc_data['tcon_id'].isdigit()


def validate_event_data(event_data, schema):
    event_data_keys = set(event_data.keys())
    schema_keys = set(schema['_attrs_order_'])
    assert event_data_keys == schema_keys


def validate_audit_op(msg, svc):
    schema = call(
        'audit.json_schemas',
        [['_name_', '=', f'audit_entry_smb_{msg["event"].lower()}']],
        {
            'select': [
                ['_attrs_order_', 'attrs'],
                ['properties.event_data', 'event_data']
            ],
        }
    )

    assert schema is not [], str(msg)
    schema = schema[0]

    for key in schema['attrs']:
        assert key in msg, str(msg)

    validate_svc_data(msg, svc)
    try:
        aid_guid = uuid.UUID(msg['audit_id'])
    except ValueError:
        raise AssertionError(f'{msg["audit_id"]}: malformed UUID')

    assert str(aid_guid) == msg['audit_id']

    try:
        sess_guid = uuid.UUID(msg['session'])
    except ValueError:
        raise AssertionError(f'{msg["session"]}: malformed UUID')

    assert str(sess_guid) == msg['session']

    validate_event_data(msg['event_data'], schema['event_data'])


def do_audit_ops(svc):
    with smb_connection(
        share=svc,
        username=SHAREUSER,
        password=PASSWD,
    ) as c:
        fd = c.create_file('testfile.txt', 'w')
        for i in range(0, 3):
            c.write(fd, b'foo')
            c.read(fd, 0, 3)
        c.close(fd, True)

    sleep(AUDIT_WAIT)
    return call('auditbackend.query', 'SMB', [['event', '!=', 'AUTHENTICATION']])


def test__audit_log(request):
    def get_event(event_list, ev_type):
        for e in event_list:
            if e['event'] == ev_type:
                return e

        return None

    with make_dataset('smb-audit', data={'share_type': 'SMB'}) as ds:
        with smb_share(os.path.join('/mnt', ds), 'SMB_AUDIT', {
            'purpose': 'LEGACY_SHARE',
            'options': {'guestok': True},
            'audit': {'enable': True}
        }) as s:
            events = do_audit_ops(s['name'])
            assert len(events) > 0

            for ev_type in ['CONNECT', 'DISCONNECT', 'CREATE', 'CLOSE', 'READ', 'WRITE']:
                assert get_event(events, ev_type) is not None, str(events)

            for event in events:
                validate_audit_op(event, s['name'])

            new_data = call('sharing.smb.update', s['id'], {'audit': {'enable': True, 'ignore_list': ['builtin_users']}})
            assert new_data['audit']['enable'], str(new_data['audit'])
            assert new_data['audit']['ignore_list'] == ['builtin_users'], str(new_data['audit'])

            # Verify that being member of group in ignore list is sufficient to avoid new messages
            # By default authentication attempts are always logged
            assert do_audit_ops(s['name']) == events

            new_data = call('sharing.smb.update', s['id'], {'audit': {'enable': True, 'watch_list': ['builtin_users']}})
            assert new_data['audit']['enable'], str(new_data['audit'])
            assert new_data['audit']['watch_list'] == ['builtin_users'], str(new_data['audit'])

            # Verify that watch_list takes precedence
            # By default authentication attempts are always logged
            new_events = do_audit_ops(s['name'])
            assert len(new_events) > len(events)

            new_data = call('sharing.smb.update', s['id'], {'audit': {'enable': False}})
            assert new_data['audit']['enable'] is False, str(new_data['audit'])
            assert new_data['audit']['ignore_list'] == [], str(new_data['audit'])
            assert new_data['audit']['watch_list'] == [], str(new_data['audit'])

            # Verify that disabling audit prevents new messages from being written
            assert do_audit_ops(s['name']) == new_events


@pytest.mark.parametrize('torture_test', [
    'local.binding',
    'local.ntlmssp',
    'local.smbencrypt',
    'local.messaging',
    'local.irpc',
    'local.strlist',
    'local.file',
    'local.str',
    'local.time',
    'local.datablob',
    'local.binsearch',
    'local.asn1',
    'local.anonymous_shared',
    'local.strv',
    'local.strv_util',
    'local.util',
    'local.idtree',
    'local.dlinklist',
    'local.genrand',
    'local.iconv',
    'local.socket',
    'local.pac',
    'local.share',
    'local.loadparm',
    'local.charset',
    'local.convert_string',
    'local.string_case_handle',
    'local.tevent_req',
    'local.util_str_escape',
    'local.talloc',
    'local.replace',
    'local.crypto.md4'
])
def test__local_torture(request, torture_test):
    ssh(f'smbtorture //127.0.0.1 {torture_test}')
