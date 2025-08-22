import contextlib
import os
import time

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd
)
import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.assets.filesystem import directory, mkfile
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.system import reset_systemd_svcs
from auto_config import ha, interface, password, user, pool_name
from functions import async_SSH_done, async_SSH_start

skip_ha_tests = pytest.mark.skipif(not (ha and "virtual_ip" in os.environ), reason="Skip HA tests")
COMMUNITY = 'public'
TRAPS = False
CONTACT = 'root@localhost.com'
LOCATION = 'Maryville, TN'
PASSWORD = 'testing1234'
SNMP_USER_NAME = 'snmpJoe'
SNMP_USER_AUTH = 'MD5'
SNMP_USER_PWD = "abcd1234"
SNMP_USER_PRIV = 'AES'
SNMP_USER_PHRS = "A priv pass phrase"
SNMP_USER_CONFIG = {
    "v3": True,
    "v3_username": SNMP_USER_NAME,
    "v3_authtype": SNMP_USER_AUTH,
    "v3_password": SNMP_USER_PWD,
    "v3_privproto": SNMP_USER_PRIV,
    "v3_privpassphrase": SNMP_USER_PHRS
}


EXPECTED_DEFAULT_CONFIG = {
    "location": "",
    "contact": "",
    "traps": False,
    "v3": False,
    "community": "public",
    "v3_username": "",
    "v3_authtype": "SHA",
    "v3_password": "",
    "v3_privproto": None,
    "v3_privpassphrase": None,
    "options": "",
    "loglevel": 3,
    "zilstat": False
}

EXPECTED_DEFAULT_STATE = {
    "enable": False,
    "state": "STOPPED",
}

CMD_STATE = {
    "RUNNING": "START",
    "STOPPED": "STOP"
}


# =====================================================================
#                     Fixtures and utilities
# =====================================================================
@pytest.fixture(scope='module')
def initialize_and_start_snmp():
    """ Initialize and start SNMP """
    try:
        # Get initial config and start SNMP
        orig_config = call('snmp.config')
        call('service.control', 'START', 'snmp', job=True)
        yield orig_config
    finally:
        # Restore default config (which will also delete any created user),
        # stop SNMP and restore default enable state
        call('snmp.update', EXPECTED_DEFAULT_CONFIG)
        call('service.control', CMD_STATE[EXPECTED_DEFAULT_STATE["state"]], 'snmp', job=True)
        call('service.update', 'snmp', {"enable": EXPECTED_DEFAULT_STATE['enable']})


@pytest.fixture(scope='class')
def add_SNMPv3_user():
    # Reset the systemd restart counter
    reset_systemd_svcs("snmpd snmp-agent")

    call('snmp.update', SNMP_USER_CONFIG)
    assert get_systemctl_status('snmp-agent') == "RUNNING"

    res = call('snmp.get_snmp_users')
    assert SNMP_USER_NAME in res
    yield


@pytest.fixture(scope='function')
def create_nested_structure():
    """
    Create the following structure:
        tank -+-> dataset_1 -+-> dataset_2 -+-> dataset_3
              |-> zvol_1a    |-> zvol-L_2a  |-> zvol L_3a
              |-> zvol_1b    |-> zvol-L_2b  |-> zvol L_3b
              |-> file_1     |-> file_2     |-> file_3
              |-> dir_1      |-> dir_2      |-> dir_3
    TODO: Make this generic and move to assets
    """
    ds_path = ""
    ds_list = []
    zv_list = []
    dir_list = []
    file_list = []
    # Test '-' and ' ' in the name (we skip index 0)
    zvol_name = ["bogus", "zvol", "zvol-L", "zvol L"]
    with contextlib.ExitStack() as es:

        for i in range(1, 4):
            preamble = f"{ds_path + '/' if i > 1 else ''}"
            vol_path = f"{preamble}{zvol_name[i]}_{i}"

            # Create zvols
            for c in crange('a', 'b'):
                zv = es.enter_context(dataset(vol_path + c, {"type": "VOLUME", "volsize": 1048576}))
                zv_list.append(zv)

            # Create directories
            d = es.enter_context(directory(f"/mnt/{pool_name}/{preamble}dir_{i}"))
            dir_list.append(d)

            # Create files
            f = es.enter_context(mkfile(f"/mnt/{pool_name}/{preamble}file_{i}", 1048576))
            file_list.append(f)

            # Create datasets
            ds_path += f"{'/' if i > 1 else ''}dataset_{i}"
            ds = es.enter_context(dataset(ds_path))
            ds_list.append(ds)

        yield {'zv': zv_list, 'ds': ds_list, 'dir': dir_list, 'file': file_list}


def crange(c1, c2):
    """
    Generates the characters from `c1` to `c2`, inclusive.
    Simple lowercase ascii only.
    NOTE: Not safe for runtime code
    """
    ord_a = 97
    ord_z = 122
    c1_ord = ord(c1)
    c2_ord = ord(c2)
    assert c1_ord < c2_ord, f"'{c1}' must be 'less than' '{c2}'"
    assert ord_a <= c1_ord <= ord_z
    assert ord_a <= c2_ord <= ord_z
    for c in range(c1_ord, c2_ord + 1):
        yield chr(c)


def get_systemctl_status(service):
    """ Return 'RUNNING' or 'STOPPED' """
    try:
        res = ssh(f'systemctl status {service}')
    except AssertionError:
        # Return code is non-zero if service is not running
        return "STOPPED"

    action = [line for line in res.splitlines() if line.lstrip().startswith('Active')]
    return "RUNNING" if action[0].split()[2] == "(running)" else "STOPPED"


def get_sysname(hostip, community):
    iterator = getCmd(SnmpEngine(),
                      CommunityData(community),
                      UdpTransportTarget((hostip, 161)),
                      ContextData(),
                      ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysName', 0)))
    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
    assert errorIndication is None, errorIndication
    assert errorStatus == 0, errorStatus
    value = str(varBinds[0])
    _prefix = "SNMPv2-MIB::sysName.0 = "
    assert value.startswith(_prefix), value
    return value[len(_prefix):]


def validate_snmp_get_sysname_uses_same_ip(hostip):
    """Test that when we query a particular interface by SNMP the response comes from the same IP."""

    # Write the test in a manner that is portable between Linux and FreeBSD ... which means
    # *not* using 'any' as the interface name.  We will use the interface supplied by the
    # test runner instead.
    print(f"Testing {hostip} ", end='')
    p = async_SSH_start(f"tcpdump -t -i {interface} -n udp port 161 -c2", user, password, hostip)
    # Give some time so that the tcpdump has started before we proceed
    time.sleep(5)

    get_sysname(hostip, COMMUNITY)

    # Now collect and process the tcpdump output
    outs, errs = async_SSH_done(p, 20)
    output = outs.strip()
    assert len(output), f"No output from tcpdump:{outs}"
    lines = output.split("\n")
    assert len(lines) == 2, f"Unexpected number of lines output by tcpdump: {outs}"
    for line in lines:
        assert line.split()[0] == 'IP'
    # print(errs)
    get_dst = lines[0].split()[3].rstrip(':')
    reply_src = lines[1].split()[1]
    assert get_dst == reply_src
    assert get_dst.endswith(".161")


def user_list_users(snmp_config):
    """Run an snmpwalk as a SNMP v3 user"""

    add_cmd = None
    if snmp_config['v3_privproto']:
        authpriv_setting = 'authPriv'
        add_cmd = f"-x {snmp_config['v3_privproto']} -X \"{snmp_config['v3_privpassphrase']}\" "
    else:
        authpriv_setting = 'authNoPriv'

    cmd = f"snmpwalk -v3 -u  {snmp_config['v3_username']} -l {authpriv_setting} "
    cmd += f"-a {snmp_config['v3_authtype']} -A {snmp_config['v3_password']} "
    if add_cmd:
        cmd += add_cmd
    cmd += "localhost iso.3.6.1.6.3.15.1.2.2.1.3"

    # This call will timeout if SNMP is not running
    res = ssh(cmd)
    return [x.split(':')[-1].strip(' \"') for x in res.splitlines()]


def v2c_snmpwalk(mib):
    """
    Run snmpwalk with v2c protocol
    mib is the item to be gathered.  mib format examples:
        iso.3.6.1.6.3.15.1.2.2.1.3
        1.3.6.1.4.1.50536.1.2
    """
    cmd = f"snmpwalk -v2c -cpublic localhost {mib}"

    # This call will timeout if SNMP is not running
    res = ssh(cmd)
    return [x.split(':')[-1].strip(' \"') for x in res.splitlines()]


# =====================================================================
#                           Tests
# =====================================================================
class TestSNMP:

    def test_configure_SNMP(self, initialize_and_start_snmp):
        config = initialize_and_start_snmp

        # We should be starting with the default config
        # Check the hard way so that we can identify the culprit
        for k, v in EXPECTED_DEFAULT_CONFIG.items():
            assert config.get(k) == v, f'Expected {k}:"{v}", but found {k}:"{config.get(k)}"'

        # Make some changes that will be checked in a later test
        call('snmp.update', {
            'community': COMMUNITY,
            'traps': TRAPS,
            'contact': CONTACT,
            'location': LOCATION
        })

    def test_enable_SNMP_service_at_boot(self):
        id = call('service.update', 'snmp', {'enable': True})
        assert isinstance(id, int)

        res = call('service.query', [['service', '=', 'snmp']])
        assert res[0]['enable'] is True

    def test_SNMP_service_is_running(self):
        res = call('service.query', [['service', '=', 'snmp']])
        assert res[0]['state'] == 'RUNNING'

    def test_SNMP_settings_are_preserved(self):
        data = call('snmp.config')
        assert data['community'] == COMMUNITY
        assert data['traps'] == TRAPS
        assert data['contact'] == CONTACT
        assert data['location'] == LOCATION

    def test_sysname_reply_uses_same_ip(self):
        validate_snmp_get_sysname_uses_same_ip(truenas_server.ip)

    @skip_ha_tests
    def test_ha_sysname_reply_uses_same_ip(self):
        validate_snmp_get_sysname_uses_same_ip(truenas_server.ip)
        validate_snmp_get_sysname_uses_same_ip(truenas_server.nodea_ip)
        validate_snmp_get_sysname_uses_same_ip(truenas_server.nodeb_ip)

    def test_SNMPv3_private_user(self):
        """
        The SNMP system user should always be available
        """
        # Reset the systemd restart counter
        reset_systemd_svcs("snmpd snmp-agent")

        # Make sure the createUser command is not present
        res = ssh("tail -2 /var/lib/snmp/snmpd.conf")
        assert 'createUser' not in res

        # Make sure the SNMP system user is a rwuser
        res = ssh("cat /etc/snmp/snmpd.conf")
        assert "rwuser snmpSystemUser" in res

        # List the SNMP users and confirm the system user
        # This also confirms the functionality of the system user
        res = call('snmp.get_snmp_users')
        assert "snmpSystemUser" in res

    @pytest.mark.parametrize('payload,attrib,errmsg', [
        ({'v3': False, 'community': ''},
            'snmp_update.community', 'This field is required when SNMPv3 is disabled'),
        ({'v3': True},
            'snmp_update.v3_username', 'This field is required when SNMPv3 is enabled'),
        ({'v3_authtype': 'AES'},
            'snmp_update.v3_authtype', 'Input should be'),
        ({'v3': True, 'v3_authtype': 'MD5'},
            'snmp_update.v3_username', 'This field is required when SNMPv3 is enabled'),
        ({'v3_password': 'short'},
            'snmp_update.v3_password', 'Password must contain at least 8 characters'),
        ({'v3_privproto': 'SHA'},
            'snmp_update.v3_privproto', 'Input should be'),
        ({'v3_privproto': 'AES'},
            'snmp_update.v3_privpassphrase', 'This field is required when SNMPv3 private protocol is specified'),
    ])
    def test_v3_validators(self, payload, attrib, errmsg):
        """
        All these configuration updates should fail.
        """
        with pytest.raises(ValidationErrors) as ve:
            call('snmp.update', payload)
        if attrib:
            assert f"{attrib}" in ve.value.errors[0].attribute
        if errmsg:
            assert f"{errmsg}" in ve.value.errors[0].errmsg

    @pytest.mark.usefixtures("add_SNMPv3_user")
    class TestSNMPv3User:
        def test_SNMPv3_user_function(self):
            res = user_list_users(SNMP_USER_CONFIG)
            assert SNMP_USER_NAME in res, f"Expected to find {SNMP_USER_NAME} in {res}"

        def test_SNMPv3_user_retained_across_service_restart(self):
            # Reset the systemd restart counter
            reset_systemd_svcs("snmpd snmp-agent")

            res = call('service.control', 'STOP', 'snmp', job=True)
            assert res is True
            res = call('service.control', 'START', 'snmp', job=True)
            assert res is True
            res = call('snmp.get_snmp_users')
            assert "snmpSystemUser" in res
            assert SNMP_USER_NAME in res

        def test_SNMPv3_user_retained_across_v3_disable(self):

            # Disable and check
            res = call('snmp.update', {'v3': False})
            assert SNMP_USER_NAME in res['v3_username']
            res = call('snmp.get_snmp_users')
            assert SNMP_USER_NAME in res

            # Enable and check
            res = call('snmp.update', {'v3': True})
            assert SNMP_USER_NAME in res['v3_username']
            res = call('snmp.get_snmp_users')
            assert SNMP_USER_NAME in res

        @pytest.mark.parametrize('key,value', [
            ('reset', ''),  # Reset systemd counters
            ('v3_username', 'ixUser'),
            ('v3_authtype', 'SHA'),
            ('v3_password', 'SimplePassword'),
            ('reset', ''),  # Reset systemd counters
            ('v3_privproto', 'DES'),
            ('v3_privpassphrase', 'Pass phrase with spaces'),
            # Restore original user name
            ('v3_username', SNMP_USER_NAME)
        ])
        def test_SNMPv3_user_changes(self, key, value):
            """
            Make changes to the SNMPv3 user name, password, etc. and confirm user function.
            This also tests a pass phrase that includes spaces.
            NOTE: We include systemd counter resets because these calls require the most restarts.
            """
            if key == 'reset':
                # Reset the systemd restart counter
                reset_systemd_svcs("snmpd snmp-agent")
            else:
                res = call('snmp.update', {key: value})
                assert value in res[key]
                assert get_systemctl_status('snmp-agent') == "RUNNING"

                # Confirm user function after change
                user_config = call('snmp.config')
                res = user_list_users(user_config)
                assert user_config['v3_username'] in res

        def test_SNMPv3_user_delete(self):

            # Make sure the user is currently present
            res = call('snmp.get_snmp_users')
            assert SNMP_USER_NAME in res

            res = call('snmp.update', {'v3': False, 'v3_username': ''})
            # v3_authtype is defaulted to 'SHA' in the DB
            assert not any([res['v3'], res['v3_username'], res['v3_password'],
                            res['v3_privproto'], res['v3_privpassphrase']]) and 'SHA' in res['v3_authtype']
            assert get_systemctl_status('snmp-agent') == "RUNNING"

            res = call('snmp.get_snmp_users')
            assert SNMP_USER_NAME not in res

            # Make sure the user cannot perform SNMP requests
            with pytest.raises(Exception) as ve:
                res = user_list_users(SNMP_USER_CONFIG)
            assert "Unknown user name" in str(ve.value)

    def test_zvol_reporting(self, create_nested_structure):
        """
        The TrueNAS snmp agent should list all zvols.
        TrueNAS zvols can be created on any ZFS pool or dataset.
        The snmp agent should list them all.
        snmpwalk -v2c -cpublic localhost 1.3.6.1.4.1.50536.1.2.1.1.2
        """
        # The expectation is that the snmp agent should list exactly the six zvols.
        created_items = create_nested_structure

        # Include a snapshot of one of the zvols
        with snapshot(created_items['zv'][0], "snmpsnap01"):
            snmp_res = v2c_snmpwalk('1.3.6.1.4.1.50536.1.2.1.1.2')
            assert all(v in created_items['zv'] for v in snmp_res), f"expected {created_items['zv']}, but found {snmp_res}"
