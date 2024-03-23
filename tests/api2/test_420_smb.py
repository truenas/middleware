import pytest
import sys
import os
from pytest_dependency import depends
import secrets
import string
import uuid
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from protocols import smb_connection
from utils import create_dataset
from auto_config import ip, pool_name
from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset as make_dataset
from middlewared.test.integration.utils import call, ssh


AUDIT_WAIT = 10
SMB_NAME = "TestCifsSMB"
SHAREUSER = 'smbuser420'
PASSWD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))
pytestmark = pytest.mark.smb


@pytest.fixture(scope='module')
def initialize_for_smb_tests(request):
    with make_dataset('smb-cifs', data={'share_type': 'SMB'}) as ds:
        with user({
            'username': SHAREUSER,
            'full_name': SHAREUSER,
            'group_create': True,
            'password': PASSWD
        }, get_instance=False):
            with smb_share(os.path.join('/mnt', ds), SMB_NAME, {
                'purpose': 'NO_PRESET',
                'guestok': True,
            }) as s:
                try:
                    call('smb.update', {
                        'enable_smb1': True,
                        'guest': SHAREUSER
                    })
                    call('service.start', 'cifs')
                    yield {'dataset': ds, 'share': s}
                finally:
                    call('smb.update', {
                        'enable_smb1': False,
                        'guest': 'nobody'
                    })
                    call('service.stop', 'cifs')


@pytest.mark.dependency(name="smb_initialized")
def test_001_enable_smb1(initialize_for_smb_tests):
    global smb_info
    global smb_id
    global test_420_ds_name
    smb_info = initialize_for_smb_tests
    smb_id = smb_info['share']['id']
    test_420_ds_name = smb_info['dataset']


@pytest.mark.parametrize('params', [
    ('SMB1', 'GUEST'),
    ('SMB2', 'GUEST'),
    ('SMB1', SHAREUSER),
    ('SMB2', SHAREUSER)
])
def test_012_test_basic_smb_ops(request, params):
    depends(request, ["smb_initialized"], scope="session")
    proto, runas = params
    with smb_connection(
        host=ip,
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


def test_018_setting_enable_smb1_to_false(request):
    depends(request, ["smb_initialized"], scope="session")
    call('smb.update', {"enable_smb1": False})


def test_019_change_sharing_smd_home_to_true_and_set_guestok_to_false(request):
    depends(request, ["smb_initialized"], scope="session")
    share = call('sharing.smb.update', smb_id, {'home': True, "guestok": False})
    try:
        share_path = call('smb.getparm', 'path', 'homes')
        assert share_path == f'{share["path_local"]}/%U'
    finally:
        new_info = call('sharing.smb.update', smb_id, {'home': False})

    share_path = call('smb.getparm', 'path', new_info['name'])
    assert share_path == share['path_local']
    obey_pam_restrictions = call('smb.getparm', 'obey pam restrictions', 'GLOBAL')
    assert obey_pam_restrictions == False


def test_034_change_timemachine_to_true(request):
    depends(request, ["smb_initialized"], scope="session")
    call('smb.update', {'aapl_extensions': True})
    call('sharing.smb.update', smb_id, {'timemachine': True})
    try:
        share_info = call('sharing.smb.query', [['id', '=', smb_id]], {'get': True})
        assert share_info['timemachine'] is True

        enabled = call('smb.getparm', 'fruit:time machine', share_info['name'])
        assert enabled == 'True'

        vfs_obj = call('smb.getparm', 'vfs objects', share_info['name'])
        assert 'fruit' in vfs_obj
    finally:
        call('sharing.smb.update', smb_id, {'timemachine': False})
        call('smb.update', {'aapl_extensions': False})


@pytest.mark.dependency(name="SMB_RECYCLE_CONFIGURED")
def test_039_enable_recycle_bin(request):
    depends(request, ["smb_initialized"], scope="session")
    share_info = call('sharing.smb.update', smb_id, {'recyclebin': True})
    vfs_obj = call('smb.getparm', 'vfs objects', share_info['name'])
    assert 'recycle' in vfs_obj


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


def test_042_recyclebin_functional_test(request):
    depends(request, ["SMB_RECYCLE_CONFIGURED"], scope="session")
    with create_dataset(f'{test_420_ds_name}/subds', {'share_type': 'SMB'}):
        with smb_connection(
            host=ip,
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
def test_043_recyclebin_functional_test_subdir(request, smb_config):
    depends(request, ["SMB_RECYCLE_CONFIGURED"], scope="session")
    tmp_ds = f"{pool_name}/recycle_test"
    tmp_ds_path = f'/mnt/{tmp_ds}/subdir'
    tmp_share_name = 'recycle_test'

    call('smb.update', smb_config['global'])
    # basic tests of recyclebin operations
    with create_dataset(tmp_ds, {'share_type': 'SMB'}):
        ssh(f'mkdir {tmp_ds_path}')
        with smb_share(tmp_ds_path, tmp_share_name, {
            'purpose': 'NO_PRESET',
            'recyclebin': True
        } | smb_config['share']):
            with smb_connection(
                host=ip,
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
            'purpose': 'NO_PRESET',
            'recyclebin': True
        } | smb_config['share']):
            with smb_connection(
                host=ip,
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


@pytest.mark.dependency(name="SID_CHANGED")
def test_056_netbios_name_change_check_sid(request):
    """
    This test changes the netbios name of the server and then
    verifies that this results in the server's domain SID changing.
    The new SID is stored in a global variable so that we can
    perform additional tests to verify that SIDs are rewritten
    properly in group_mapping.tdb. old_netbiosname is stored so
    that we can reset configuration to what it was prior to the test.

    Test failure here shows that we failed to write our new SID
    to the configuration database.
    """
    depends(request, ["smb_initialized"], scope="session")
    global new_sid
    global old_netbiosname

    smb_config = call('smb.config')
    old_netbiosname = smb_config['netbiosname']
    old_sid = smb_config['cifs_SID']

    new_sid = call('smb.update', {'netbiosname': 'nb_new'})['cifs_SID']
    assert new_sid != old_sid


@pytest.mark.dependency(name="SID_TEST_GROUP")
def test_057_create_new_smb_group_for_sid_test(request):
    """
    Create testgroup and verify that groupmap entry generated
    with new SID.
    """
    def check_groupmap_for_entry(groupmaps, nt_name):
        for entry in groupmaps:
            if entry['nt_name'] == nt_name:
                return entry

        return None

    depends(request, ["SID_CHANGED"], scope="session")
    global smb_group_id

    with group({'name': 'testsidgroup', 'smb': True}):
        groupmaps = call('smb.groupmap_list')

        test_entry = check_groupmap_for_entry(
            groupmaps['local'].values(),
            'testsidgroup'
        )
        assert test_entry is not None, groupmaps['local'].values()
        domain_sid = test_entry['sid'].rsplit("-", 1)[0]
        assert domain_sid == new_sid, groupmaps['local'].values()

        call('smb.update', {'netbiosname': old_netbiosname})

        groupmaps = call('smb.groupmap_list')
        test_entry = check_groupmap_for_entry(
            groupmaps['local'].values(),
            'testsidgroup'
        )

        assert test_entry is not None, groupmaps['local'].values()
        domain_sid = test_entry['sid'].rsplit("-", 1)[0]
        assert domain_sid != new_sid, groupmaps['local'].values()


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
        host=ip,
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


def test_060_audit_log(request):
    def get_event(event_list, ev_type):
        for e in event_list:
            if e['event'] == ev_type:
                return e

        return None

    depends(request, ["smb_initialized"], scope="session")
    with make_dataset('smb-audit', data={'share_type': 'SMB'}) as ds:
        with smb_share(os.path.join('/mnt', ds), 'SMB_AUDIT', {
            'purpose': 'NO_PRESET',
            'guestok': True,
            'audit': {'enable': True}
        }) as s:
            events = do_audit_ops(s['name'])
            assert len(events) > 0

            for ev_type in ['CONNECT', 'DISCONNECT', 'CREATE', 'CLOSE', 'READ', 'WRITE']:
                assert get_event(events, ev_type) is not None, str(events)

            for event in events:
                validate_audit_op(event, s['name'])

            new_data = call('sharing.smb.update', s['id'], {'audit': {'ignore_list': ['builtin_users']}})
            assert new_data['audit']['enable'], str(new_data['audit'])
            assert new_data['audit']['ignore_list'] == ['builtin_users'], str(new_data['audit'])

            # Verify that being member of group in ignore list is sufficient to avoid new messages
            # By default authentication attempts are always logged
            assert do_audit_ops(s['name']) == events

            new_data = call('sharing.smb.update', s['id'], {'audit': {'watch_list': ['builtin_users']}})
            assert new_data['audit']['enable'], str(new_data['audit'])
            assert new_data['audit']['ignore_list'] == ['builtin_users'], str(new_data['audit'])
            assert new_data['audit']['watch_list'] == ['builtin_users'], str(new_data['audit'])

            # Verify that watch_list takes precedence
            # By default authentication attempts are always logged
            new_events = do_audit_ops(s['name'])
            assert len(new_events) > len(events)

            new_data = call('sharing.smb.update', s['id'], {'audit': {'enable': False}})
            assert new_data['audit']['enable'] is False, str(new_data['audit'])
            assert new_data['audit']['ignore_list'] == ['builtin_users'], str(new_data['audit'])
            assert new_data['audit']['watch_list'] == ['builtin_users'], str(new_data['audit'])

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
def test_065_local_torture(request, torture_test):
    ssh(f'smbtorture //127.0.0.1 {torture_test}')
