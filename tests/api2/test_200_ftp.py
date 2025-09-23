import contextlib
import copy
import json
import os
import subprocess
from ftplib import all_errors, error_temp
from time import sleep
from timeit import default_timer as timer
from types import SimpleNamespace

import pytest
from pytest_dependency import depends

from assets.websocket.server import reboot
from middlewared.test.integration.assets.account import user as ftp_user
from middlewared.test.integration.assets.pool import dataset as dataset_asset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server, host as init_truenas_server

from auto_config import password, pool_name, user
from functions import SSH_TEST, send_file
from protocols import ftp_connect, ftp_connection, ftps_connection

FTP_DEFAULT = {}
DB_DFLT = {}
INIT_DIRS_AND_FILES = {
    'path': None,
    'dirs': [
        {'name': 'init_dir'},
        {'name': 'init_ro_dir', 'perm': '-w',
         'contents': ["ReadOnlyDir_file1", "ReadOnlyDir_file2"]}
    ],
    'files': [{'name': 'init_file', 'contents': "Contents of init_file"},
              {'name': 'init_ro_file', 'contents': "RO data", 'perm': '-w'}],
}


# ================= Utility Functions ==================

@pytest.fixture(scope='module')
def confirm_test_config():
    if truenas_server.ip is None:
        # Fix-up truenas_server
        init_truenas_server()
    assert truenas_server.ip is not None


@pytest.fixture(scope='module')
def ftp_init_db_dflt(confirm_test_config):
    # Get the 'default' settings from FTPModel
    ftpconf_script = '#!/usr/bin/python3\n'
    ftpconf_script += 'import json\n'
    ftpconf_script += 'from middlewared.plugins.ftp import FTPModel\n'
    ftpconf_script += 'FTPModel_defaults = {}\n'
    ftpconf_script += 'for attrib in FTPModel.__dict__.keys():\n'
    ftpconf_script += '    if attrib[:4] == "ftp_":\n'
    ftpconf_script += '        try:\n'
    ftpconf_script += '            val = getattr(getattr(FTPModel, attrib), "default").arg\n'
    ftpconf_script += '        except AttributeError:\n'
    ftpconf_script += '            val = None\n'
    ftpconf_script += '        if not callable(val):\n'
    ftpconf_script += '            FTPModel_defaults[attrib] = val\n'
    ftpconf_script += 'print(json.dumps(FTPModel_defaults))\n'
    cmd_file = open('ftpconf.py', 'w')
    cmd_file.writelines(ftpconf_script)
    cmd_file.close()
    results = send_file('ftpconf.py', 'ftpconf.py', user, password, truenas_server.ip)
    assert results['result'], str(results['output'])
    rv_defaults = SSH_TEST("python3 ftpconf.py", user, password)
    assert rv_defaults['result'], str(rv_defaults)
    global FTP_DEFAULT
    FTP_DEFAULT = json.loads(rv_defaults['stdout'].strip())

    # clean up the temporary script
    os.remove('ftpconf.py')
    results = SSH_TEST('rm ftpconf.py', user, password)
    assert results['result'] is True, results

    # # Special cases: The default banner is in a file (see proftpd.conf.mako)
    assert FTP_DEFAULT['ftp_banner'] is None, FTP_DEFAULT['ftp_banner']

    # Make the default model keys match the DB names
    global DB_DFLT
    DB_DFLT = {k.replace('ftp_', ''): FTP_DEFAULT[k] for k in FTP_DEFAULT}
    return DB_DFLT


def ftp_set_config(config={}):
    # Fixup some settings
    if config != {}:
        tmpconf = config.copy()
        if 'banner' in tmpconf and tmpconf['banner'] is None:
            tmpconf['banner'] = ""
        if 'anonpath' in tmpconf and tmpconf['anonpath'] is False:
            tmpconf['anonpath'] = ""
        if 'masqaddress' in tmpconf and tmpconf['masqaddress'] is None:
            tmpconf['masqaddress'] = ''
        if 'ssltls_certificate_id' in tmpconf and tmpconf['ssltls_certificate_id'] is None:
            tmpconf.pop('ssltls_certificate_id')
        if 'options' in tmpconf and tmpconf['options'] is None:
            tmpconf['options'] = ''
        call('ftp.update', tmpconf)


def parse_conf_file(file='proftpd'):
    results = SSH_TEST(f"cat /etc/proftpd/{file}.conf", user, password)
    assert results['result'], str(results)
    lines = results['stdout'].splitlines()

    rv = {}
    context = [{'server': None}]
    for line in lines:
        line = line.lstrip()
        if not line or line.startswith('#'):
            continue

        # Keep track of contexts
        if line.startswith('<'):
            if line[1] == "/":
                context.pop()
                continue
            else:
                c = line.split()[0][1:]
                v = line.split()[1][:-1] if len(line.split()) > 1 else None
                context.append({c: v})
                continue

        # Process the directive
        if 1 < len(line.strip().split()):
            # Trap TransferRate directive
            if "TransferRate" == line.split()[0]:
                tmp = line.split()
                directive = ' '.join(tmp[:2])
                value = ' '.join(tmp[2:])
            else:
                directive, value = line.strip().split(maxsplit=1)
        else:
            directive = line.strip()
            value = None
        entry = {directive: [copy.deepcopy(context), value]}
        rv.update(entry)
    return rv


def query_ftp_service():
    return call('service.query', [['service', '=', 'ftp']], {'get': True})


def validate_proftp_conf():
    '''
    Confirm FTP configuration settings
    NB: Avoid calling this for localuser* and anonuser* in the same test
    '''
    xlat = {True: "on", False: "off"}
    # Retrieve result from the database
    ftpConf = call('ftp.config')
    parsed = parse_conf_file('proftpd')

    # Sanity spot check settings in proftpd.conf
    assert ftpConf['port'] == int(parsed['Port'][1])
    assert ftpConf['clients'] == int(parsed['MaxClients'][1]), f"\nftpConf={ftpConf}\nparsed={parsed}"
    assert ftpConf['ipconnections'] == int(parsed['MaxConnectionsPerHost'][1])
    assert ftpConf['loginattempt'] == int(parsed['MaxLoginAttempts'][1])
    assert ftpConf['timeout'] == int(parsed['TimeoutIdle'][1])
    assert ftpConf['timeout_notransfer'] == int(parsed['TimeoutNoTransfer'][1])

    # Confirm that rootlogin has been removed.
    assert ftpConf.get('rootlogin') is None

    if ftpConf['onlyanonymous']:
        assert 'User' in parsed
        assert ftpConf['anonpath'] == parsed['User'][0][1]['Anonymous'], f"parsed['User'] = {parsed['User']}"
        assert parsed['UserAlias'][1] == 'anonymous ftp'
        assert parsed['Group'][1] == 'ftp'
        assert 'LOGIN' == parsed['AllowAll'][0][2]['Limit'], \
            f"AllowAll must be within <imit LOGIN>, {parsed['AllowAll']}"
    else:
        assert parsed['User'][1] == 'nobody'

    if ftpConf['onlylocal']:
        assert 'AllowAll' in parsed
        assert 'LOGIN' == parsed['AllowAll'][0][1]['Limit'], \
            f"AllowAll must be within <imit LOGIN>, {parsed['AllowAll']}"
    else:
        if not ftpConf['onlyanonymous']:
            assert 'AllowAll' not in parsed

    # The absence of onlyanonymous and onlyonly mean some settings are present
    if not (ftpConf['onlyanonymous'] or ftpConf['onlylocal']):
        assert 'DenyAll' in parsed
        assert 'LOGIN' == parsed['DenyAll'][0][1]['Limit']
        # Confirm rootlogin has been removed.
        assert 'root' not in parsed['AllowGroup']

    # The banner is saved to a file
    rv_motd = SSH_TEST("cat /etc/proftpd/proftpd.motd", user, password)
    assert rv_motd['result'], str(rv_motd)
    motd = rv_motd['stdout'].strip()
    if ftpConf['banner']:
        assert motd == ftpConf['banner'], f"\nproftpd.motd = \'{motd}\'\nbanner = \'{ftpConf['banner']}\'"

    expect_umask = f"{ftpConf['filemask']} {ftpConf['dirmask']}"
    assert expect_umask == parsed['Umask'][1], \
        f"Found unexpected Umask entry: expected '{expect_umask}', found '{parsed['Umask'][1]}'"
    assert xlat[ftpConf['fxp']] == parsed['AllowForeignAddress'][1]
    if ftpConf['resume']:
        assert xlat[ftpConf['resume']] == parsed['AllowRetrieveRestart'][1]
        assert xlat[ftpConf['resume']] == parsed['AllowStoreRestart'][1]

    # The DefaultRoot setting is defined completly in proftpd.conf.mako as '~ !root'
    if ftpConf['defaultroot']:
        assert parsed['DefaultRoot'][1] == "~ !root"

    assert xlat[ftpConf['ident']] == parsed['IdentLookups'][1]
    assert xlat[ftpConf['reversedns']] == parsed['UseReverseDNS'][1]

    if ftpConf['masqaddress']:
        assert ftpConf['masqaddress'] == parsed['MasqueradeAddress'][1]

    if ftpConf['passiveportsmin']:
        expect_setting = f"{ftpConf['passiveportsmin']} {ftpConf['passiveportsmax']}"
        assert expect_setting == parsed['PassivePorts'][1], \
            f"Found unexpected PassivePorts entry: expected '{expect_setting}', found '{parsed['PassivePorts'][1]}'"

    if ftpConf['localuserbw']:
        assert ftpConf['localuserbw'] == int(parsed['TransferRate STOR'][1])
    if ftpConf['localuserdlbw']:
        assert ftpConf['localuserdlbw'] == int(parsed['TransferRate RETR'][1])
    if ftpConf['anonuserbw']:
        assert ftpConf['anonuserbw'] == int(parsed['TransferRate STOR'][1])
    if ftpConf['anonuserdlbw']:
        assert ftpConf['anonuserdlbw'] == int(parsed['TransferRate RETR'][1])

    if ftpConf['tls']:
        parsed = parsed | parse_conf_file('tls')

        # These two are 'fixed' settings in proftpd.conf.mako, but they are important
        assert parsed['TLSEngine'][1] == 'on'
        assert parsed['TLSProtocol'][1] == 'TLSv1.2 TLSv1.3'

        if 'TLSOptions' in parsed:
            # Following the same method from proftpd.conf.mako
            tls_options = []
            for k, v in [
                ('allow_client_renegotiations', 'AllowClientRenegotiations'),
                ('allow_dot_login', 'AllowDotLogin'),
                ('allow_per_user', 'AllowPerUser'),
                ('common_name_required', 'CommonNameRequired'),
                ('enable_diags', 'EnableDiags'),
                ('export_cert_data', 'ExportCertData'),
                ('no_empty_fragments', 'NoEmptyFragments'),
                ('no_session_reuse_required', 'NoSessionReuseRequired'),
                ('stdenvvars', 'StdEnvVars'),
                ('dns_name_required', 'dNSNameRequired'),
                ('ip_address_required', 'iPAddressRequired'),
            ]:
                if ftpConf[f'tls_opt_{k}']:
                    tls_options.append(v)

            assert set(tls_options) == set(parsed['TLSOptions'][1].split()), \
                f"--- Unexpected difference ---\ntls_options:\n{set(tls_options)}"\
                f"\nparsed['TLSOptions']\n{set(parsed['TLSOptions'][1].split())}"
        assert ftpConf['tls_policy'] == parsed['TLSRequired'][1]
        # Do a sanity check on the certificate entries
        assert 'TLSRSACertificateFile' in parsed
        assert 'TLSRSACertificateKeyFile' in parsed
    # Return the current welcome message
    return ftpConf, motd


@contextlib.contextmanager
def ftp_configure(changes=None):
    '''
    Apply requested FTP configuration changes.
    Restore original setting when done
    '''
    changes = changes or {}
    ftpConf = call('ftp.config')
    restore_keys = set(ftpConf) & set(changes)
    restore_items = {key: ftpConf[key] for key in restore_keys}
    if changes:
        try:
            call('ftp.update', changes)
            yield
        finally:
            # Restore settings
            call('ftp.update', restore_items)
            # Validate the restore
            validate_proftp_conf()


def ftp_set_service_enable_state(state=None):
    '''
    Get and return the current state struct
    Set the requested state
    '''
    restore_setting = None
    if state is not None:
        assert isinstance(state, bool)
        # save current setting
        restore_setting = query_ftp_service()['enable']
        # update to requested setting
        call('service.update', 'ftp', {'enable': state})

    return restore_setting


@contextlib.contextmanager
def ftp_server(service_state=None):
    '''
    Start FTP server with current config
    Stop server when done
    '''
    # service 'enable' state
    if service_state is not None:
        restore_state = ftp_set_service_enable_state(service_state)

    try:
        # Start FTP service
        call('service.control', 'START', 'ftp', {'silent': False}, job=True)
        yield
    finally:
        # proftpd can core dump if stopped while it's busy
        # processing a prior config change. Give it a sec.
        sleep(1)
        call('service.control', 'STOP', 'ftp', {'silent': False}, job=True)
        # Restore original service state
        if service_state is not None:
            ftp_set_service_enable_state(restore_state)


@contextlib.contextmanager
def ftp_anon_ds_and_srvr_conn(dsname='ftpdata', FTPconfig=None, useFTPS=None, withConn=None, **kwargs):
    FTPconfig = FTPconfig or {}
    withConn = withConn or True

    with dataset_asset(dsname, **kwargs) as ds:
        ds_path = f"/mnt/{ds}"

        # Add files and dirs
        ftp_dirs_and_files = INIT_DIRS_AND_FILES.copy()
        ftp_dirs_and_files['path'] = ds_path
        ftp_init_dirs_and_files(ftp_dirs_and_files)

        with ftp_server():
            anon_config = {
                "onlyanonymous": True,
                "anonpath": ds_path,
                "onlylocal": False,
                **FTPconfig
            }
            with ftp_configure(anon_config):
                ftpConf, motd = validate_proftp_conf()
                if withConn:
                    with (ftps_connection if useFTPS else ftp_connection)(truenas_server.ip) as ftp:
                        yield SimpleNamespace(ftp=ftp, dirs_and_files=ftp_dirs_and_files,
                                              ftpConf=ftpConf, motd=motd)


@contextlib.contextmanager
def ftp_user_ds_and_srvr_conn(dsname='ftpdata', username="FTPlocal", FTPconfig=None, useFTPS=False, **kwargs):
    FTPconfig = FTPconfig or {}

    with dataset_asset(dsname, **kwargs) as ds:
        ds_path = f"/mnt/{ds}"
        with ftp_user({
            "username": username,
            "group_create": True,
            "home": ds_path,
            "full_name": username + " User",
            "password": "secret",
            "home_create": False,
            "smb": False,
            "groups": [call('group.query', [['name', '=', 'ftp']], {'get': True})['id']],
        }):
            # Add dirs and files
            ftp_dirs_and_files = INIT_DIRS_AND_FILES.copy()
            ftp_dirs_and_files['path'] = ds_path
            ftp_init_dirs_and_files(ftp_dirs_and_files)

            with ftp_server():
                with ftp_configure(FTPconfig):
                    ftpConf, motd = validate_proftp_conf()
                    with (ftps_connection if useFTPS else ftp_connection)(truenas_server.ip) as ftp:
                        yield SimpleNamespace(ftp=ftp, dirs_and_files=ftp_dirs_and_files, ftpConf=ftpConf, motd=motd)


def ftp_get_users():
    '''
    Return a list of active users
    NB: ftp service should be running when called
    '''
    ssh_out = SSH_TEST("ftpwho -o json", user, password)
    assert ssh_out['result'], str(ssh_out)
    output = ssh_out['output']
    # Strip off trailing bogus data
    joutput = output[:output.rindex('}') + 1]
    whodata = json.loads(joutput)
    return whodata['connections']


# For resume xfer test
def upload_partial(ftp, src, tgt, NumKiB=128):
    with open(src, 'rb') as file:
        ftp.voidcmd('TYPE I')
        with ftp.transfercmd(f'STOR {os.path.basename(tgt)}', None) as conn:
            blksize = NumKiB // 8
            for xfer in range(0, 8):
                # Send some of the file
                buf = file.read(1024 * blksize)
                assert buf, "Unexpected local read error"
                conn.sendall(buf)


def download_partial(ftp, src, tgt, NumKiB=128):
    with open(tgt, 'wb') as file:
        ftp.voidcmd('TYPE I')
        with ftp.transfercmd(f'RETR {os.path.basename(src)}', None) as conn:
            NumXfers = NumKiB // 8
            for xfer in range(0, NumXfers):
                # Receive and write some of the file
                data = conn.recv(8192)
                assert data, "Unexpected receive error"
                file.write(data)


def ftp_upload_binary_file(ftpObj, source, target, offset=None):
    """
    Upload a file to the FTP server
    INPUT:
        source is the full-path to local file
        target is the name to use on the FTP server
    RETURN:
        Elapsed time to upload file

    """
    assert ftpObj is not None
    assert source is not None
    assert target is not None

    with open(source, 'rb') as fp:
        if offset:
            fp.seek(offset)
        start = timer()
        ftpObj.storbinary(f'STOR {os.path.basename(target)}', fp, rest=offset)
        et = timer() - start
        return et


def ftp_download_binary_file(ftpObj, source, target, offset=None):
    """
    Download a file from the FTP server
    INPUT:
        source is the name of the file on the FTP server
        target is full-path name on local host
    RETURN:
        Elapsed time to download file
    """
    assert ftpObj is not None
    assert source is not None
    assert target is not None
    opentype = 'ab' if offset else 'wb'

    with open(target, opentype) as fp:
        start = timer()
        ftpObj.retrbinary(f'RETR {os.path.basename(source)}', fp.write, rest=offset)
        et = timer() - start
        return et


def ftp_create_local_file(LocalPathName="", content=None):
    '''
    Create a local file
    INPUT:
        If 'content' is:
        - None, then create with touch
        - 'int', then it represents the size in KiB to fill with random data
        - 'str', then write that to the file
        If 'content is not None, 'int' or 'str', then assert
    RETURN:
        tuple: (size_in_bytes, sha256_checksum)
    '''
    assert LocalPathName != "", "empty file name"
    b = '' if isinstance(content, str) else 'b'
    # Create a local file
    with open(LocalPathName, 'w' + b) as f:
        if (content is None) or isinstance(content, str):
            content = content or ""
            f.write(content)
        elif isinstance(content, int):
            f.write(os.urandom(1024 * content))
        else:
            assert True, f"Cannot create with content: '{content}'"
    # Confirm existence
    assert os.path.exists(LocalPathName)
    localsize = os.path.getsize(LocalPathName)

    res = subprocess.run(["sha256sum", LocalPathName], capture_output=True)
    local_chksum = res.stdout.decode().split()[0]
    return (localsize, local_chksum)


def ftp_create_remote_file(RemotePathName="", content=None):
    '''
    Create a remote file
    INPUT:
        If 'content' is:
        - None, then create with touch
        - 'int', then it represents the size in KiB to fill with random data
        - 'str', then write that to the file
        If 'content is not None, 'int' or 'str', then assert
    RETURN:
        tuple: (size_in_bytes, sha256_checksum)
    '''
    assert RemotePathName != "", "empty file name"
    if content is None:
        ssh(f'touch {RemotePathName}')
    elif isinstance(content, int):
        ssh(f"dd if=/dev/urandom of={RemotePathName} bs=1K count={content}", complete_response=True)
    elif isinstance(content, str):
        ssh(f'echo "{content}" > {RemotePathName}')
    else:
        assert True, f"Cannot create with content: '{content}'"

    # Get and return the details
    remotesize = ssh(f"du -b {RemotePathName}").split()[0]
    remote_chksum = ssh(f"sha256sum {RemotePathName}").split()[0]
    return (remotesize, remote_chksum)


def ftp_init_dirs_and_files(items=None):
    if items is not None:
        assert items['path'] is not None
        path = items['path']
        for d in items['dirs']:
            res = SSH_TEST(f"mkdir -p {path}/{d['name']}", user, password)
            assert res['result'], str(res)
            thispath = f"{path}/{d['name']}"
            if 'contents' in d:
                for f in d['contents']:
                    res = SSH_TEST(f"touch {thispath}/{f}", user, password)
                    assert res['result'], str(res)
            if 'perm' in d:
                res = SSH_TEST(f"chmod {d['perm']} {thispath}", user, password)
                assert res['result'], str(res)

        for f in items['files']:
            res = SSH_TEST(f"echo \'{f['contents']}\' > \'{path}/{f['name']}\'", user, password)
            assert res['result'], str(res)
            if 'perm' in f:
                res = SSH_TEST(f"chmod {f['perm']} {path}/{f['name']}", user, password)
                assert res['result'], str(res)


def init_test_data(type='unknown', data=None):
    assert data is not None
    new_test_data = {}
    new_test_data['type'] = type
    new_test_data['ftp'] = data.ftp
    new_test_data['ftpConf'] = data.ftpConf
    new_test_data['motd'] = data.motd
    new_test_data['dirs_and_files'] = data.dirs_and_files
    return new_test_data


def ftp_ipconnections_test(test_data=None, *extra):
    '''
    Test FTP MaxConnectionsPerHost conf setting.
    The DB equivalent is ipconnections.
    NB1: This is called with an existing connection
    '''
    assert test_data['ftp'] is not None
    ftpConf = test_data['ftpConf']
    ConnectionLimit = int(ftpConf['ipconnections'])
    # We already have one connection
    NumConnects = 1
    NewConnects = []
    while NumConnects < ConnectionLimit:
        try:
            ftpConn = ftp_connect(truenas_server.ip)
        except all_errors as e:
            assert False, f"Unexpected connection error: {e}"
        NewConnects.append(ftpConn)
        NumConnects += 1
        CurrentFtpUsers = ftp_get_users()
        assert len(CurrentFtpUsers) == ConnectionLimit
    try:
        # This next connect should fail
        ftp_connect(truenas_server.ip)
    except all_errors as e:
        # An expected error
        assert NumConnects == ConnectionLimit
        assert e.args[0].startswith('530')
        assert f"maximum number of connections ({ConnectionLimit})" in e.args[0]
    finally:
        # Clean up extra connections
        for conn in NewConnects:
            conn.quit()


def ftp_dir_listing_test(test_data=None, *extra):
    '''
    Get a directory listing
    '''

    assert test_data is not None
    ftp = test_data['ftp']
    listing = [name for name, facts in list(ftp.mlsd())]
    expected = test_data['dirs_and_files']
    # Get expected
    for f in expected['files']:
        assert f['name'] in listing, f"Did not find {f['name']}"
    for d in expected['dirs']:
        assert f['name'] in listing, f"Did not find {f['name']}"


def ftp_download_files_test(test_data=None, run_data=None):
    '''
    Retrieve files from server and confirm contents
    '''

    assert test_data is not None
    ftp = test_data['ftp']
    expected_contents = None
    for f in run_data:
        if f['contents'] is None:
            continue
        expected_contents = f['contents']
        found_contents = []
        cmd = f"RETR {f['name']}"
        try:
            res = ftp.retrlines(cmd, found_contents.append)
            assert f['expect_to_pass'] is True, \
                f"Expected file download failure for {f['name']}, but passed: {f}"
            assert res.startswith('226 Transfer complete'), "Detected download failure"
            assert expected_contents in found_contents
        except all_errors as e:
            assert f['expect_to_pass'] is False, \
                f"Expected file download success for {f['name']}, but failed: {e.args}"


def ftp_upload_files_test(test_data=None, run_data=None):
    '''
    Upload files to the server
    '''
    localfile = "/tmp/ftpfile"

    assert test_data is not None
    assert run_data != []
    ftp = test_data['ftp']
    try:
        for f in run_data:
            if 'content' in f and isinstance(f['content'], str):
                ftp_create_local_file(localfile, f['content'])
            with open(localfile, 'rb') as tmpfile:
                try:
                    cmd = f"STOR {f['name']}"
                    res = ftp.storlines(cmd, tmpfile)
                    assert f['expect_to_pass'] is True, \
                        f"Expected file add failure for {f['name']}, but passed: {f}"
                    assert res.startswith('226 Transfer complete'), "Detected upload failure"
                except all_errors as e:
                    assert f['expect_to_pass'] is False, \
                        f"Expected file add success for {f['name']}, but failed: {e.args}"
    finally:
        # Clean up
        if os.path.exists(localfile):
            os.remove(localfile)


def ftp_delete_files_test(test_data=None, run_data=None):
    '''
    Delete files on the server
    '''
    assert test_data is not None
    assert run_data != []
    ftp = test_data['ftp']
    for f in run_data:
        try:
            ftp.delete(f['name'])
            assert f['expect_to_pass'] is True, \
                f"Expected file delete failure for {f['name']}, but passed: {f}"
        except all_errors as e:
            assert f['expect_to_pass'] is False, \
                f"Expected file delete success for {f['name']}, but failed: {e.args}"


def ftp_add_dirs_test(test_data=None, run_data=None):
    '''
    Create directories on the server
    '''
    assert test_data is not None
    assert run_data != []
    ftp = test_data['ftp']
    for d in run_data:
        try:
            res = ftp.mkd(d['name'])
            assert d['name'] in res
        except all_errors as e:
            assert d['expect_to_pass'] is False, \
                f"Expected deletion success for {d['name']}, but failed: {e.args}"


def ftp_remove_dirs_test(test_data=None, run_data=None):
    '''
    Delete directories on the server
    '''
    assert test_data is not None
    assert run_data != []
    ftp = test_data['ftp']
    for d in run_data:
        try:
            ftp.rmd(d['name'])
            assert d['expect_to_pass'] is True, \
                f"Expected deletion failure for {d['name']}, but passed: {d}"
        except all_errors as e:
            assert d['expect_to_pass'] is False, \
                f"Expected deletion success for {d['name']}, but failed: {e.args}"

#
# ================== TESTS =========================
#


@pytest.mark.dependency(name='init_dflt_config')
def test_001_validate_default_configuration(request, ftp_init_db_dflt):
    '''
    Confirm the 'default' settings in the DB are in sync with what
    is specified in the FTPModel class.  These can get out of sync
    with migration code.
    NB1: This expects FTP to be in the default configuration
    '''
    ftp_set_config(DB_DFLT)

    with ftp_server():
        # Get the DB settings
        db = call('ftp.config')

        # Check each setting
        diffs = {}
        for setting in set(DB_DFLT) & set(db):
            # Special cases: ftp_anonpath is 'nullable' in the DB, but the default is False
            if setting == "anonpath" and (db[setting] == '' or db[setting] is None):
                db[setting] = False
            # Special cases: Restore 'None' for empty string
            if setting in ['banner', 'options', 'masqaddress'] and db[setting] == '':
                db[setting] = None

            if DB_DFLT[setting] != db[setting]:
                diffs.update({setting: [DB_DFLT[setting], db[setting]]})

        assert len(diffs) == 0, f"Found mismatches: [DB_DFLT, db]\n{diffs}"


def test_005_ftp_service_at_boot(request):
    '''
    Confirm we can enable FTP service at boot and restore current setting
    '''
    # Get the current state and set the new state
    restore_setting = ftp_set_service_enable_state(True)
    assert restore_setting is False, f"Unexpected service at boot setting: enable={restore_setting}, expected False"

    # Confirm we toggled the setting
    res = query_ftp_service()['enable']
    assert res is True, res

    # Restore original setting
    ftp_set_service_enable_state(restore_setting)


def test_010_ftp_service_start(request):
    '''
    Confirm we can start the FTP service with the default config
    Confirm the proftpd.conf file was generated
    '''
    # Start FTP service
    with ftp_server():
        # Validate the service is running via our API
        assert query_ftp_service()['state'] == 'RUNNING'

        # Confirm we have /etc/proftpd/proftpd.conf
        rv_conf = SSH_TEST("ls /etc/proftpd/proftpd.conf", user, password)
        assert rv_conf['result'], str(rv_conf)


def test_015_ftp_configuration(request):
    '''
    Confirm config changes get reflected in proftpd.conf
    '''
    depends(request, ["init_dflt_config"], scope="session")

    with ftp_server():
        changes = {
            'clients': 100,
            'ipconnections': 10,
            'loginattempt': 100,
            'banner': 'A banner to remember',
            'onlylocal': True,
            'fxp': True
        }
        with ftp_configure(changes):
            validate_proftp_conf()


def test_017_ftp_port(request):
    '''
    Confirm config changes get reflected in proftpd.conf
    '''
    depends(request, ["init_dflt_config"], scope="session")

    with ftp_server():
        assert query_ftp_service()['state'] == 'RUNNING'

        # Confirm FTP is listening on the default port
        res = SSH_TEST("ss -tlpn", user, password)
        sslist = res['output'].splitlines()
        ftp_entry = [line for line in sslist if "ftp" in line]
        ftpPort = ftp_entry[0].split()[3][2:]
        assert ftpPort == "21", f"Expected default FTP port, but found {ftpPort}"

        # Test port change
        changes = {'port': 22222}
        with ftp_configure(changes):
            validate_proftp_conf()
            res = SSH_TEST("ss -tlpn", user, password)
            sslist = res['output'].splitlines()
            ftp_entry = [line for line in sslist if "ftp" in line]
            ftpPort = ftp_entry[0].split()[3][2:]
            assert ftpPort == "22222", f"Expected '22222' FTP port, but found {ftpPort}"


# @pytest.mark.parametrize("NumTries,expect_to_pass"m )
@pytest.mark.parametrize('NumFailedTries,expect_to_pass', [
    (2, True),
    (3, False)
])
def test_020_login_attempts(request, NumFailedTries, expect_to_pass):
    '''
    Test our ability to change and trap excessive failed login attempts
    1) Test good password before running out of tries
    2) Test good password after running out of tries
    '''
    depends(request, ["init_dflt_config"], scope="session")
    login_setup = {
        "onlylocal": True,
        "loginattempt": 3,
    }
    with ftp_user_ds_and_srvr_conn('ftplocalDS', 'FTPfatfingeruser', login_setup) as loginftp:
        MaxTries = loginftp.ftpConf['loginattempt']
        ftpObj = loginftp.ftp
        for login_attempt in range(0, NumFailedTries):
            try:
                # Attempt login with bad password
                ftpObj.login(user='FTPfatfingeruser', passwd="secrfet")
            except all_errors as all_e:
                assert True, f"Unexpected login failure: {all_e}"
            except EOFError as eof_e:
                assert True, f"Unexpected disconnect: {eof_e}"
        if expect_to_pass:
            # Try with correct password
            ftpObj.login(user='FTPfatfingeruser', passwd="secret")
            assert expect_to_pass is True
        else:
            with pytest.raises(Exception):
                # Try with correct password, but already exceeded number of tries
                ftpObj.login(user='FTPfatfingeruser', passwd="secret")
                assert login_attempt < MaxTries, "Failed to limit login attempts"


def test_030_root_login(request):
    '''
    "Allow Root Login" setting has been removed.
    Confirm we block root login.
    '''
    depends(request, ["init_dflt_config"], scope="session")
    with ftp_anon_ds_and_srvr_conn('anonftpDS') as ftpdata:
        ftpObj = ftpdata.ftp
        try:
            res = ftpObj.login(user, password)
            assert True, f"Unexpected behavior: root login was supposed to fail, but login response is {res}"

        except all_errors:
            pass


@pytest.mark.parametrize('setting,ftpConfig', [
    (True, {"onlyanonymous": True, "anonpath": "anonftpDS", "onlylocal": False}),
    (False, {"onlyanonymous": False, "anonpath": "", "onlylocal": True}),
])
def test_031_anon_login(request, setting, ftpConfig):
    '''
    Test the WebUI "Allow Anonymous Login" setting.
    In our DB the setting is "onlyanonymous" and an "Anonymous" section in proftpd.conf.
    '''
    depends(request, ["init_dflt_config"], scope="session")
    if setting is True:
        # Fixup anonpath
        ftpConfig['anonpath'] = f"/mnt/{pool_name}/{ftpConfig['anonpath']}"
    with ftp_anon_ds_and_srvr_conn('anonftpDS', ftpConfig) as ftpdata:
        ftpObj = ftpdata.ftp
        try:
            res = ftpObj.login()
            assert setting is True, \
                f"Unexpected behavior: onlyanonymous={ftpConfig['onlyanonymous']}, but login successfull: {res}"

            # The following assumes the login was successfull
            assert res.startswith('230')
            ftpusers = ftp_get_users()
            assert 'ftp' == ftpusers[0]['user']
        except all_errors as e:
            assert setting is False, f"Unexpected failure, onlyanonymous={setting}, but got {e}"


@pytest.mark.parametrize('localuser,expect_to_pass', [
    ("FTPlocaluser", True),
    ("BadUser", False)
])
def test_032_local_login(request, localuser, expect_to_pass):
    depends(request, ["init_dflt_config"], scope="session")
    with ftp_user_ds_and_srvr_conn('ftplocalDS', 'FTPlocaluser', {"onlylocal": True}) as ftpdata:
        ftpObj = ftpdata.ftp
        try:
            ftpObj.login(localuser, 'secret')
            assert expect_to_pass, f"Unexpected behavior: {user} should not have been allowed to login"
        except all_errors as e:
            assert not expect_to_pass, f"Unexpected behavior: {user} should have been allowed to login. {e}"


def test_040_reverse_dns(request):
    depends(request, ["init_dflt_config"], scope="session")
    ftp_conf = {"onlylocal": True, "reversedns": True}
    with ftp_user_ds_and_srvr_conn('ftplocalDS', 'FTPlocaluser', ftp_conf) as ftpdata:
        ftpObj = ftpdata.ftp
        try:
            ftpObj.login('FTPlocaluser', 'secret')
        except all_errors as e:
            assert False, f"Login failed with reverse DNS enabled. {e}"


@pytest.mark.parametrize('masq_type, expect_to_pass',
                         [("hostname", True), ("ip_addr", True), ("invalid.domain", False)])
def test_045_masquerade_address(request, masq_type, expect_to_pass):
    '''
    TrueNAS tooltip:
        Public IP address or hostname. Set if FTP clients cannot connect through a NAT device.
    We test masqaddress with: hostname, IP address and an invalid fqdn.
    '''
    depends(request, ["init_dflt_config"], scope="session")
    netconfig = call('network.configuration.config')
    if masq_type == 'hostname':
        masqaddr = netconfig['hostname']
        if netconfig['domain'] and netconfig['domain'] != "local":
            masqaddr = masqaddr + "." + netconfig['domain']
    elif masq_type == 'ip_addr':
        masqaddr = truenas_server.ip
    else:
        masqaddr = masq_type

    ftp_conf = {"onlylocal": True, "masqaddress": masqaddr}
    with pytest.raises(Exception) if not expect_to_pass else contextlib.nullcontext():
        with ftp_user_ds_and_srvr_conn('ftplocalDS', 'FTPlocaluser', ftp_conf) as ftpdata:
            ftpObj = ftpdata.ftp
            try:
                ftpObj.login('FTPlocaluser', 'secret')
                res = ftpObj.sendcmd('PASV')
                assert res.startswith("227 Entering Passive Mode")
                srvr_ip, p1, p2 = res.split('(', 1)[1].split(')')[0].rsplit(',', 2)
                srvr_ip = srvr_ip.replace(',', '.')
                # If the masquerade is our hostname the presented IP address will
                # be the 'local' IP address
                if masq_type == "hostname":
                    assert srvr_ip == '127.0.0.1'
                else:
                    assert srvr_ip == truenas_server.ip
            except all_errors as e:
                assert False, f"FTP failed with masqaddres = '{masqaddr}'. {e}"


@pytest.mark.parametrize('testing,ftpConfig,expect_to_pass', [
    ("config", {"passiveportsmin": 100}, False),
    ("config", {"passiveportsmin": 3000, "passiveportsmax": 2000}, False),
    ("config", {"passiveportsmin": 2000, "passiveportsmax": 2000}, False),
    ("run", {"passiveportsmin": 22222, "passiveportsmax": 22223}, True),
])
def test_050_passive_ports(request, testing, ftpConfig, expect_to_pass):
    '''
    Test the passive port range setting.
    NB: The proFTPd documentation for this setting states:
        | Should no open ports be found within the configured range, the server will default
        | to a random kernel-assigned port, and a message logged.
    '''
    depends(request, ["init_dflt_config"], scope="session")
    if testing == 'config':
        try:
            with ftp_configure(ftpConfig):
                assert expect_to_pass is True
        except Exception as e:
            assert expect_to_pass is False, f"{e['error']}"
    else:
        with ftp_anon_ds_and_srvr_conn('anonftpDS', ftpConfig) as ftpdata:
            ftpObj = ftpdata.ftp
            try:
                res = ftpObj.login()
                # The confirm the login was successfull
                assert res.startswith('230')
                res = ftpObj.sendcmd('PASV')
                assert res.startswith("227 Entering Passive Mode")
                # The response includes the server IP and passive port
                # Convert '227 Entering Passive Mode (a,b,c,d,e,f)' to ['a,b,c,d', 'e', 'f']
                srvr_ip, p1, p2 = res.split('(', 1)[1].split(')')[0].rsplit(',', 2)
                # Calculate the passive port
                pasv_port = int(p1) * 256 + int(p2)
                assert srvr_ip.replace(',', '.') == truenas_server.ip
                assert pasv_port == ftpdata.ftpConf['passiveportsmin']
            except all_errors as e:
                assert expect_to_pass is False, f"Unexpected failure, {e}"


def test_055_no_activity_timeout(request):
    '''
    Test the WebUI "Timeout" setting.  In our DB it is "timeout" and "TimeoutIdle" in proftpd.conf.
        | The TimeoutIdle directive configures the maximum number of seconds that proftpd will
        ! allow clients to stay connected without receiving any data on either the control or data connection
    '''
    depends(request, ["init_dflt_config"], scope="session")
    with ftp_anon_ds_and_srvr_conn('anonftpDS', {'timeout': 3}) as ftpdata:
        ftpObj = ftpdata.ftp
        try:
            ftpObj.login()
            sleep(ftpdata.ftpConf['timeout'] + 1)
            ftpObj.nlst()
            assert False, "Unexpected behavior: 'Activity Timeout' did not occur.  "\
                          "Expected listing to fail, but it succeeded."
        except all_errors as e:
            chkstr = f"Idle timeout ({ftpdata.ftpConf['timeout']} seconds)"
            assert chkstr in str(e), e


def test_056_no_xfer_timeout(request):
    '''
    This tests the WebUI "Notransfer Timeout" setting.  In our DB it is "timeout_notransfer"
    and "TimeoutNoTranfer" in proftpd.conf.
        | The TimeoutNoTransfer directive configures the maximum number of seconds a client
        | is allowed to spend connected, after authentication, without issuing a data transfer command
        | which results in a data connection (i.e. sending/receiving a file, or requesting a directory listing)
    '''
    depends(request, ["init_dflt_config"], scope="session")
    with ftp_anon_ds_and_srvr_conn('anonftpDS', {'timeout_notransfer': 3}) as ftpdata:
        ftpObj = ftpdata.ftp
        try:
            ftpObj.login()
            sleep(ftpdata.ftpConf['timeout_notransfer'] + 1)
            ftpObj.nlst()
            assert False, "Unexpected behavior: 'No Transfer Timeout' did not occur.  "\
                          "Expected listing to fail, but it succeeded."
        except all_errors as e:
            chkstr = f"No transfer timeout ({ftpdata.ftpConf['timeout_notransfer']} seconds)"
            assert chkstr in str(e), e


@pytest.mark.flaky(reruns=5, reruns_delay=5)  # Can sometimes getoside the range
@pytest.mark.parametrize('testwho,ftp_setup_func', [
    ('anon', ftp_anon_ds_and_srvr_conn),
    ('local', ftp_user_ds_and_srvr_conn),
])
def test_060_bandwidth_limiter(request, testwho, ftp_setup_func):
    FileSize = 1024  # KiB
    ulRate = 64  # KiB
    dlRate = 128  # KiB
    ulConf = testwho + 'userbw'
    dlConf = testwho + 'userdlbw'

    depends(request, ["init_dflt_config"], scope="session")
    ftp_anon_bw_limit = {
        ulConf: ulRate,  # upload limit
        dlConf: dlRate   # download limit
    }
    ftpfname = "BinaryFile"

    with ftp_setup_func(FTPconfig=ftp_anon_bw_limit) as ftpdata:
        ftpObj = ftpdata.ftp
        localfname = f"/tmp/{ftpfname}"
        if testwho == 'anon':
            results = SSH_TEST(f"chown ftp {ftpdata.ftpConf['anonpath']}", user, password)
            assert results['result'] is True, results
        try:
            if testwho == 'anon':
                ftpObj.login()
            else:
                ftpObj.login('FTPlocal', 'secret')
            ftpObj.voidcmd('TYPE I')

            # Create local binary file
            with open(localfname, 'wb') as f:
                f.write(os.urandom(1024 * FileSize))

            ElapsedTime = int(ftp_upload_binary_file(ftpObj, localfname, ftpfname))
            xfer_rate = FileSize // ElapsedTime
            # This typically will match exactly, but in actual testing this might vary
            assert (ulRate - 8) <= xfer_rate <= (ulRate + 20), \
                f"Failed upload rate limiter: Expected {ulRate}, but sensed rate is {xfer_rate}"

            ElapsedTime = int(ftp_download_binary_file(ftpObj, ftpfname, localfname))
            xfer_rate = FileSize // ElapsedTime
            # Allow for variance
            assert (dlRate - 8) <= xfer_rate <= (dlRate + 20), \
                f"Failed download rate limiter: Expected {dlRate}, but sensed rate is {xfer_rate}"
        except all_errors as e:
            assert False, f"Unexpected failure: {e}"
        finally:
            # Clean up
            if os.path.exists(localfname):
                os.remove(localfname)


@pytest.mark.parametrize('fmask,f_expect,dmask,d_expect', [
    ("000", "0666", "000", "0777"),
    ("007", "0660", "002", "0775"),
])
def test_065_umask(request, fmask, f_expect, dmask, d_expect):
    depends(request, ["init_dflt_config"], scope="session")
    localfile = "/tmp/localfile"
    fname = "filemask" + fmask
    dname = "dirmask" + dmask
    ftp_create_local_file(localfile, "Contents of local file")

    ftp_umask = {
        'filemask': fmask,
        'dirmask': dmask
    }
    with ftp_anon_ds_and_srvr_conn('anonftpDS', ftp_umask, mode='777') as ftpdata:
        ftpObj = ftpdata.ftp
        try:
            ftpObj.login()

            # Add file and make a directory
            with open(localfile, 'rb') as tmpfile:
                res = ftpObj.storlines(f'STOR {fname}', tmpfile)
                assert "Transfer complete" in res

            res = ftpObj.mkd(dname)
            assert dname in res

            ftpdict = dict(ftpObj.mlsd())
            assert ftpdict[fname]['unix.mode'] == f_expect, ftpdict[fname]
            assert ftpdict[dname]['unix.mode'] == d_expect, ftpdict[dname]

        except all_errors as e:
            assert False, f"Unexpected failure: {e}"
        finally:
            # Clean up
            if os.path.exists(localfile):
                os.remove(localfile)


@pytest.mark.dependency(depends=['init_dflt_config'])
@pytest.mark.parametrize(
    'ftpConf,expect_to_pass', [
        ({}, False),
        ({'resume': True}, True)
    ],
    ids=[
        "resume xfer: blocked",
        "resume xfer: allowed"
    ]
)
@pytest.mark.parametrize(
    'direction,create_src,xfer_partial,xfer_remainder', [
        ('upload', ftp_create_local_file, upload_partial, ftp_upload_binary_file),
        ('download', ftp_create_remote_file, download_partial, ftp_download_binary_file)
    ],
    ids=[
        "upload",
        "download"
    ]
)
def test_070_resume_xfer(
    ftpConf, expect_to_pass, direction, create_src, xfer_partial, xfer_remainder
):

    # # ---------- helper functions ---------
    def get_tgt_size(ftp, tgt, direction):
        if direction == 'upload':
            ftp.voidcmd('TYPE I')
            return ftp.size(os.path.basename(tgt))
        else:
            return os.path.getsize(tgt)

    def get_tgt_chksum(tgt, direction):
        if direction == 'upload':
            return ssh(f"sha256sum {tgt}").split()[0]
        else:
            res = subprocess.run(["sha256sum", tgt], capture_output=True)
            assert res.returncode == 0
            return res.stdout.decode().split()[0]

    try:
        # Run test
        with ftp_anon_ds_and_srvr_conn('anonftpDS', ftpConf, withConn=False, mode='777') as ftpdata:
            src_path = {'upload': "/tmp", 'download': f"{ftpdata.ftpConf['anonpath']}"}
            tgt_path = {'upload': f"{ftpdata.ftpConf['anonpath']}", "download": "/tmp"}

            # xfer test
            try:
                # Create a 1MB source binary file.
                src_pathname = '/'.join([src_path[direction], 'srcfile'])
                tgt_pathname = '/'.join([tgt_path[direction], 'tgtfile'])
                src_size, src_chksum = create_src(src_pathname, 1024)

                ftpObj = ftp_connect(truenas_server.ip)
                ftpObj.login()
                xfer_partial(ftpObj, src_pathname, tgt_pathname, 768)

                # Quit to simulate loss of connection
                try:
                    ftpObj.quit()
                except error_temp:
                    # May generate a quit error that we ignore for this test
                    pass
                ftpObj = None
                sleep(1)

                # Attempt resume to complete the upload
                ftpObj = ftp_connect(truenas_server.ip)
                ftpObj.login()
                xfer_remainder(ftpObj, src_pathname, tgt_pathname, get_tgt_size(ftpObj, tgt_pathname, direction))
            except all_errors as e:
                assert not expect_to_pass, f"Unexpected failure in resumed {direction} test: {e}"
                if not expect_to_pass:
                    assert "Restart not permitted" in str(e), str(e)

            if expect_to_pass:
                # Check upload result
                tgt_size = get_tgt_size(ftpObj, tgt_pathname, direction)
                assert int(tgt_size) == int(src_size), \
                    f"Failed {direction} size test. Expected {src_size}, found {tgt_size}"
                tgt_chksum = get_tgt_chksum(tgt_pathname, direction)
                assert src_chksum == tgt_chksum, \
                    f"Failed {direction} checksum test. Expected {src_chksum}, found {tgt_chksum}"

    finally:
        try:
            [os.remove(file) for file in ['/tmp/srcfile', '/tmp/tgtfile']]
        except OSError:
            pass


class UserTests:
    """
    Run the same suite of tests for all users
    """
    ftp_user_tests = [
        (ftp_dir_listing_test, []),
        (ftp_ipconnections_test, []),
        (ftp_download_files_test, [
            {'name': 'init_file', 'contents': "Contents of init_file", 'expect_to_pass': True},
            {'name': 'init_ro_file', 'contents': "RO data", 'expect_to_pass': True},
        ]),
        (ftp_upload_files_test, [
            {'name': 'DeleteMeFile', 'content': 'To be deleted', 'expect_to_pass': True},
            {'name': 'init_ro_file', 'expect_to_pass': False},
        ]),
        (ftp_delete_files_test, [
            {'name': 'DeleteMeFile', 'expect_to_pass': True},
            {'name': 'bogus_file', 'expect_to_pass': False},
            {'name': 'init_ro_dir/ReadOnlyDir_file1', 'expect_to_pass': False},
        ]),
        (ftp_add_dirs_test, [
            {'name': 'DeleteMeDir', 'expect_to_pass': True},
        ]),
        (ftp_remove_dirs_test, [
            {'name': 'DeleteMeDir', 'expect_to_pass': True},
            {'name': 'bogus_dir', 'expect_to_pass': False},
            {'name': 'init_ro_dir', 'expect_to_pass': False},
        ])
    ]

    @pytest.mark.parametrize("user_test,run_data", ftp_user_tests)
    def test_080_ftp_user(self, setup, user_test, run_data):
        try:
            user_test(setup, run_data)
        except all_errors as e:
            assert e is None, f"FTP error: {e}"


class TestAnonUser(UserTests):
    """
    Create a dataset with some data to be used for anonymous FTP
    Start FTP server configured for anonymous
    Create an anonymous FTP connection and login
    """
    @pytest.fixture(scope='class')
    def setup(self, request):
        depends(request, ["init_dflt_config"], scope="session")

        with ftp_anon_ds_and_srvr_conn('anonftpDS') as anonftp:
            # Make the directory owned by the anonymous ftp user
            anon_path = anonftp.dirs_and_files['path']
            results = SSH_TEST(f"chown ftp {anon_path}", user, password)
            assert results['result'] is True, results
            login_error = None
            ftpObj = anonftp.ftp
            try:
                res = ftpObj.login()
                assert res.startswith('230 Anonymous access granted')
                # anonymous clients should not get the welcome message
                assert anonftp.motd.splitlines()[0] not in res

                # Run anonymous user tests with updated data
                yield init_test_data('Anon', anonftp)
            except all_errors as e:
                login_error = e
            assert login_error is None


class TestLocalUser(UserTests):

    @pytest.fixture(scope='class')
    def setup(self, request):
        depends(request, ["init_dflt_config"], scope="session")

        local_setup = {
            "onlylocal": True,
        }
        with ftp_user_ds_and_srvr_conn('ftplocalDS', 'FTPlocaluser', local_setup) as localftp:
            login_error = None
            ftpObj = localftp.ftp
            try:
                res = ftpObj.login(user='FTPlocaluser', passwd="secret")
                assert res.startswith('230')
                # local users should get the welcome message
                assert localftp.motd.splitlines()[0] in res
                ftpusers = ftp_get_users()
                assert "FTPlocaluser" == ftpusers[0]['user']

                # Run the user tests with updated data
                yield init_test_data('Local', localftp)
            except all_errors as e:
                login_error = e
            assert login_error is None


class TestFTPSUser(UserTests):

    @pytest.fixture(scope='class')
    def setup(self, request):
        depends(request, ["init_dflt_config"], scope="session")

        # We include tls_opt_no_session_reuse_required because python
        # ftplib has a long running issue with support for it.
        tls_setup = {
            "tls": True,
            "tls_opt_no_session_reuse_required": True,
            "ssltls_certificate": 1
        }
        with ftp_user_ds_and_srvr_conn('ftpslocalDS', 'FTPSlocaluser', tls_setup, useFTPS=True) as tlsftp:
            ftpsObj = tlsftp.ftp
            login_error = None
            try:
                res = ftpsObj.login(user='FTPSlocaluser', passwd="secret")
                assert res.startswith('230')
                # local users should get the welcome message
                assert tlsftp.motd.splitlines()[0] in res
                ftpusers = ftp_get_users()
                assert "FTPSlocaluser" == ftpusers[0]['user']

                # Run the user tests with updated data
                yield init_test_data('FTPS', tlsftp)
            except all_errors as e:
                login_error = e
            assert login_error is None


@pytest.mark.skip(reason="Enable this when Jenkins infrastructure is better able to handle this test")
def test_085_ftp_service_starts_after_reboot():
    '''
    NAS-123024
    There is a bug in the Debian Bookwork proftpd install package
    that enables proftpd.socket which blocks proftpd.service from starting.

    We fixed this by disabling proftpd.socket. There is a different fix
    in a Bookworm update that involves refactoring the systemd unit files.
    '''
    with ftp_server(True):  # start ftp and configure it to start at boot
        rv = query_ftp_service()
        assert rv['state'] == 'RUNNING'
        assert rv['enable'] is True

        reboot(truenas_server.ip)

        # wait for box to reboot
        max_wait = 60
        ftp_state = None
        for retry in range(max_wait):
            try:
                ftp_state = query_ftp_service()
                break
            except Exception:
                sleep(1)
                continue

        # make sure ftp service started after boot
        assert ftp_state, 'Failed to query ftp service state after {max_wait!r} seconds'
        assert ftp_state['state'] == 'RUNNING', f'Expected ftp service to be running, found {ftp_state["state"]!r}'


def test_100_ftp_service_stop():
    call('service.control', 'STOP', 'ftp', {'silent': False}, job=True)
    rv = query_ftp_service()
    assert rv['state'] == 'STOPPED'
    assert rv['enable'] is False
