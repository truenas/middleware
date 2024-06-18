import os
import subprocess

from cryptography.fernet import Fernet
from logging import getLogger
from middlewared.service import CallError
from middlewared.utils.crypto import generate_string

LOGGER = getLogger(__name__)


class SNMPSystem():
    # This is an snmpd auto-generated file.  We use it to create the SNMPv3 users.
    PRIV_CONF = '/var/lib/snmp/snmpd.conf'

    # SNMP System User authentication
    PRIV_KEY = None

    # SNMP System User info
    SYSTEM_USER = {
        'name': 'snmpSystemUser', 'auth_type': 'SHA', 'key': None, 'size': 0
    }


def _get_authuser_secret():
    """
    Get the auth user saved secret.
    Internal helper function for use by this module.
    Return decoded string.
    """
    secret = ""
    if not SNMPSystem.SYSTEM_USER['key']:
        # No system user key registered
        LOGGER.debug("No system user key is registered")
        return secret

    if SNMPSystem.PRIV_KEY:
        secret = Fernet(SNMPSystem.SYSTEM_USER['key']).decrypt(SNMPSystem.PRIV_KEY).decode()

    return secret


def _set_authuser_secret(secret):
    """
    Save the auth user secret.
    Internal helper function for use by this module.
    INPUT: ascii string (not encoded)
    """
    SNMPSystem.PRIV_KEY = Fernet(SNMPSystem.SYSTEM_USER['key']).encrypt(secret.encode())  # noqa: (F841, assigned but not used)

    return


def _add_system_user():
    """
    Add the v3 system user.
    For internal use by this module.
    NOTES: SNMP must be stopped before calling.
           The private config file is assumed to be in a regenerated state with no v3 users
    """
    SNMPSystem.SYSTEM_USER['key'] = Fernet.generate_key()
    auth_pwd = generate_string(32)

    priv_config = {
        'v3_username': SNMPSystem.SYSTEM_USER['name'],
        'v3_authtype': SNMPSystem.SYSTEM_USER['auth_type'],
        'v3_password': f"{auth_pwd}"
    }

    add_snmp_user(priv_config)

    _set_authuser_secret(auth_pwd)


def add_snmp_user(snmp):
    """
    Build the createUser message and add it to the private config file.
    NOTE: The SNMP daemon should be stopped before calling this routine and
            the new user will be available after starting SNMP.
    """
    # The private config file must exist, i.e. SNMP must have been started at least once
    if not os.path.exists(SNMPSystem.PRIV_CONF):
        return

    # BuilSNMPSystem. 'createUser' message
    create_v3_user = f"createUser {snmp['v3_username']} "

    user_pwd = snmp['v3_password']
    create_v3_user += f'{snmp["v3_authtype"]} "{user_pwd}" '

    if snmp.get('v3_privproto'):
        user_phrase = snmp['v3_privpassphrase']
        create_v3_user += f'{snmp["v3_privproto"]} "{user_phrase}" '

    create_v3_user += '\n'

    # Example: createUser newPrivUser MD5 "abcd1234" DES "abcd1234"
    with open(SNMPSystem.PRIV_CONF, 'a') as f:
        f.write(create_v3_user)


def delete_snmp_user(user):
    """
    Delete the SNMPv3 user
    RETURN: stdout message
    NOTE: SNMP must be running for this call to succeed
    """
    if pwd := _get_authuser_secret():
        # snmpusm -v3 -l authPriv -u JoeUser -a MD5 -A "abcd1234" -x AES -X "A pass phrase" localhost delete JoeUser
        cmd = [
            'snmpusm', '-v3', '-u', f'{SNMPSystem.SYSTEM_USER["name"]}',
            '-l', 'authNoPriv', '-a', f'{SNMPSystem.SYSTEM_USER["auth_type"]}', '-A', f'{pwd}',
            'localhost', 'delete', user
        ]
        # This call will timeout if SNMP is not running
        subprocess.run(cmd, capture_output=True)
    else:
        raise CallError


def get_users_cmd():
    cmd = []
    if pwd := _get_authuser_secret():
        # snmpwalk -v3 -u ixAuthUser -l authNoPriv -a MD5 -A "abcd1234" localhost iso.3.6.1.6.3.15.1.2.2.1.3
        cmd = ['snmpwalk', '-v3', '-u', f'{SNMPSystem.SYSTEM_USER["name"]}',
               '-l', 'authNoPriv', '-a', f'{SNMPSystem.SYSTEM_USER["auth_type"]}', '-A', f'{pwd}',
               'localhost', 'iso.3.6.1.6.3.15.1.2.2.1.3']
    else:
        LOGGER.debug("Unable to get authuser secret")

    return cmd
