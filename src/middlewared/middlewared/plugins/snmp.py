import middlewared.sqlalchemy as sa
import subprocess
import os

from contextlib import suppress
from cryptography.fernet import Fernet
from middlewared.common.ports import ServicePortDelegate
from middlewared.schema import Bool, Dict, Int, Password, Str
from middlewared.service import private, SystemServiceService, ValidationErrors
from middlewared.utils.crypto import generate_string
from middlewared.validators import Email, Match, Or, Range

SNMP_PRIV_CONF = '/var/lib/snmp/snmpd.conf'
SNMP_PRIV_KEY = '/var/lib/private/snmp'
_SNMP_SYSTEM_USER = {
    'name': 'snmpSystemUser', 'auth_type': 'SHA', 'key': None, 'size': 0
}


class SNMPModel(sa.Model):
    __tablename__ = 'services_snmp'

    id = sa.Column(sa.Integer(), primary_key=True)
    snmp_location = sa.Column(sa.String(255))
    snmp_contact = sa.Column(sa.String(120))
    snmp_traps = sa.Column(sa.Boolean(), default=False)
    snmp_v3 = sa.Column(sa.Boolean(), default=False)
    snmp_community = sa.Column(sa.String(120), default='public')
    snmp_v3_username = sa.Column(sa.String(20))
    snmp_v3_authtype = sa.Column(sa.String(3), default='SHA')
    snmp_v3_password = sa.Column(sa.EncryptedText())
    snmp_v3_privproto = sa.Column(sa.String(3), nullable=True)
    snmp_v3_privpassphrase = sa.Column(sa.EncryptedText(), nullable=True)
    snmp_options = sa.Column(sa.Text())
    snmp_loglevel = sa.Column(sa.Integer(), default=3)
    snmp_zilstat = sa.Column(sa.Boolean(), default=False)


class SNMPService(SystemServiceService):

    class Config:
        service = 'snmp'
        service_verb = 'restart'
        datastore = 'services.snmp'
        datastore_prefix = 'snmp_'
        cli_namespace = 'service.snmp'

    ENTRY = Dict(
        'snmp_entry',
        Str('location', required=True),
        Str('contact', required=True, validators=[Or(Email(), Match(r'^[-_a-zA-Z0-9\s]*$'))]),
        Bool('traps', required=True),
        Bool('v3', required=True),
        Str('community', validators=[Match(r'^[-_.a-zA-Z0-9\s]*$')], default='public', required=True),
        Str('v3_username', max_length=20, required=True),
        Str('v3_authtype', enum=['', 'MD5', 'SHA'], required=True),
        Password('v3_password', required=True),
        Str('v3_privproto', enum=[None, 'AES', 'DES'], null=True, required=True),
        Password('v3_privpassphrase', required=True, null=True),
        Int('loglevel', validators=[Range(min_=0, max_=7)], required=True),
        Str('options', max_length=None, required=True),
        Bool('zilstat', required=True),
        Int('id', required=True),
    )

    @private
    def _is_snmp_running(self):
        """ Internal helper function for use by this module """
        current_state = self.middleware.call_sync(
            'service.query', [["service", "=", "snmp"]], {"select": ["state"]}
        )[0]['state']
        return True if current_state == 'RUNNING' else False

    @private
    def _get_authuser_secret(self) -> str:
        """
        Get the auth user saved secret.
        Internal helper function for use by this module.
        Return decoded string.
        """
        secret = ""
        if not _SNMP_SYSTEM_USER['key']:
            self.logger.warning("No system user key registered")
            return secret

        try:
            with open(SNMP_PRIV_KEY, 'rb') as fd:
                secret_c = fd.read(_SNMP_SYSTEM_USER['size'])
        except FileNotFoundError:
            self.logger.warning("Did not find %r", SNMP_PRIV_KEY)
            return None

        try:
            secret = Fernet(_SNMP_SYSTEM_USER['key']).decrypt(secret_c).decode()
        except TypeError:
            self.logger.warning("Could not extract system user secret")

        return secret

    @private
    def _set_authuser_secret(self, secret):
        """
        Save the auth user secret.
        Internal helper function for use by this module.
        INPUT: ascii string (not encoded)
        """
        secret_c = Fernet(_SNMP_SYSTEM_USER['key']).encrypt(secret.encode())
        with open(SNMP_PRIV_KEY, 'wb') as fd:
            _SNMP_SYSTEM_USER['size'] = fd.write(secret_c)

        return

    @private
    def get_snmp_users(self):
        """
        NOTE: This should be called with SNMP running
        Use snmpwalk and the SNMP system user to get the list
        """
        users = []
        if not self._is_snmp_running():
            self.logger.debug("SNMP is not RUNNING")
            return users

        if pwd := self._get_authuser_secret():
            # snmpwalk -v3 -u ixAuthUser -l authNoPriv -a MD5 -A "abcd1234" localhost iso.3.6.1.6.3.15.1.2.2.1.3
            cmd = ['snmpwalk', '-v3', '-u', f'{_SNMP_SYSTEM_USER["name"]}',
                   '-l', 'authNoPriv', '-a', f'{_SNMP_SYSTEM_USER["auth_type"]}', '-A', f'{pwd}',
                   'localhost', 'iso.3.6.1.6.3.15.1.2.2.1.3']
            try:
                # This call will timeout if SNMP is not running
                res = subprocess.run(cmd, capture_output=True)
                users = [x.split()[-1].strip('\"') for x in res.stdout.decode().splitlines()]
            except Exception:
                self.logger.warning("Failed to list snmp v3 users")

        return users

    @private
    def add_snmp_user(self, snmp):
        """
        Build the createUser message and add it to the private config file.
        NOTE: The SNMP daemon should be stopped before calling this routine and
              the new user will be available after starting SNMP.
        """
        # The private config file must exist, i.e. SNMP must have been started at least once
        if not os.path.exists(SNMP_PRIV_CONF):
            return

        # Build the 'createUser' message
        create_v3_user = f"createUser {snmp['v3_username']} "

        user_pwd = snmp['v3_password']
        create_v3_user += f'{snmp["v3_authtype"]} "{user_pwd}" '

        if snmp.get('v3_privproto'):
            user_phrase = snmp['v3_privpassphrase']
            create_v3_user += f'{snmp["v3_privproto"]} "{user_phrase}" '

        create_v3_user += '\n'

        # Example: createUser newPrivUser MD5 "abcd1234" DES "abcd1234"
        with open(SNMP_PRIV_CONF, 'a') as f:
            f.write(create_v3_user)

    @private
    def delete_snmp_user(self, user):
        """
        Delete the SNMPv3 user
        RETURN: stdout message
        NOTE: SNMP must be running for this to be successful
              This removes the user from the SNMP db and private config _only_.
              The proper method to delete a user is to call the snmp.update routine with
              'v3' disabled and 'v3_username' cleared.
        """

        if not self._is_snmp_running():
            return "SNMP not running"

        if pwd := self._get_authuser_secret():
            # snmpusm -v3 -l authPriv -u JoeUser -a MD5 -A "abcd1234" -x AES -X "A pass phrase" localhost delete JoeUser
            cmd = ['snmpusm', '-v3', '-u', f'{_SNMP_SYSTEM_USER["name"]}',
                   '-l', 'authNoPriv', '-a', f'{_SNMP_SYSTEM_USER["auth_type"]}', '-A', f'{pwd}',
                   'localhost', 'delete', user]
            try:
                # This call will timeout if SNMP is not running
                res = subprocess.run(cmd, capture_output=True)
                retmsg = res.stdout.decode()
            except Exception:
                self.logger.warning("Failed to delete SNMPv3 user: %r", user)
                retmsg = res.stderr.decode()

        return retmsg

    @private
    def get_defaults(self):
        """
        Get default config settings.
        Fixup nullable strings
        """
        SNMPModel_defaults = {}
        prefix = self._config.datastore_prefix
        for attrib in SNMPModel.__dict__.keys():
            if attrib.startswith(prefix):
                try:
                    val = getattr(getattr(SNMPModel, attrib), "default").arg
                except AttributeError:
                    nullable = getattr(getattr(SNMPModel, attrib), "nullable")
                    val = "" if not nullable and isinstance(attrib, str) else None
                if not callable(val):
                    SNMPModel_defaults[attrib.lstrip(prefix)] = val
        return SNMPModel_defaults

    @private
    def _reset_v3_settings(self, snmp):
        """
        Reset v3 settings to default
        Internal helper function for use by this module
        """

        # Restore the 'v3_*' settings to default.  We allow only one v3 user
        config_default = self.get_defaults()
        default_v3_config = {k: v for (k, v) in config_default.items() if k.startswith('v3')}

        snmp.update(default_v3_config)
        return snmp

    @private
    def _add_system_user(self):
        """
        Add the v3 system user.
        For internal use by this module.
        NOTES: SNMP must be stopped before calling.
               The private config file is assumed to be in a regenerated state with no v3 users
        """
        if self._is_snmp_running():
            self.logger.warning("Could not add system user.  SNMP is running")
            return

        _SNMP_SYSTEM_USER['key'] = Fernet.generate_key()
        auth_pwd = generate_string(32)

        priv_config = {'v3_username': _SNMP_SYSTEM_USER['name'],
                       'v3_authtype': _SNMP_SYSTEM_USER['auth_type'],
                       'v3_password': f"{auth_pwd}"}

        self.add_snmp_user(priv_config)

        self._set_authuser_secret(auth_pwd)

    @private
    def init_v3_user(self):
        """
        Purpose: Make sure we have configured the snmpAuthUser
        This is called at init and in runtime if we need to repair the v3 users
        This will start and stop SNMP as needed.
        NOTE: This will raise CallError if SNMP is unable to be started

        Process:
            1) Record current SNMP run state
            2) Stop SNMP and delete the private config file
            3) Start SNMP to regenerate a new config file without any v3 users
            4) Stop SNMP and add v3 user markers to the private config
            5) Start SNMP to integrate the v3 users
            6) Restore SNMP to 'current' run state
        """

        config = self.middleware.call_sync('snmp.config')

        # 1) Record current SNMP run state
        snmp_service = self.middleware.call_sync("service.query", [("service", "=", "snmp")], {"get": True})

        # 2) Stop SNMP and delete the private config file
        self.middleware.call_sync("service.stop", "snmp")
        with suppress(FileNotFoundError):
            os.remove(SNMP_PRIV_CONF)

        # 3) Start SNMP to regenerate a new config file without any v3 users
        self.middleware.call_sync('service.start', 'snmp')

        # 4) Stop SNMP and add v3 user markers to the private config
        self.middleware.call_sync("service.stop", "snmp")
        self._add_system_user()

        # if configured, add the v3 user
        if config['v3_username']:
            self.add_snmp_user(config)

        # 5) Start SNMP to integrate the v3 users
        self.middleware.call_sync('service.start', 'snmp')

        # 6) Restore SNMP to 'current' run state
        if snmp_service['state'] == "STOPPED":
            self.middleware.call_sync("service.stop", "snmp")

    async def do_update(self, data):
        """
        Update SNMP Service Configuration.

        --- Rules ---
        Enabling v3:
            requires v3_username, v3_authtype and v3_password
        Disabling v3:
            By itself will retain the v3 user settings and config in the 'private' config,
            but remove the entry in the public config to block v3 access by that user.
        Disabling v3 and clearing the v3_username:
            This will do the actions described in 'Disabling v3' and take the extra step to
            remove the user from the 'private' config.

        The 'v3_*' settings are valid and enforced only when 'v3' is enabled
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        # If not v3, then must have a community 'passcode'
        if not new['v3'] and not new['community']:
            verrors.add('snmp_update.community', 'This field is required when SNMPv3 is disabled')

        # If v3, then must supply a username, authtype and password
        if new['v3']:
            # All _nearly_ the same, but different field IDs.
            if not new['v3_username']:
                verrors.add('snmp_update.v3_username', 'This field is required when SNMPv3 is enabled')
            if not new['v3_authtype']:
                verrors.add('snmp_update.v3_authtype', 'This field is required when SNMPv3 is enabled')
            if not new['v3_password']:
                verrors.add('snmp_update.v3_password', 'This field is required when SNMPv3 is enabled')

        # Get the above fixed first
        verrors.check()

        if new['v3_password'] and len(new['v3_password']) < 8:
            verrors.add('snmp_update.v3_password', 'Password must contain at least 8 characters')

        if new['v3_privproto'] and not new['v3_privpassphrase']:
            verrors.add(
                'snmp_update.v3_privpassphrase', 'This field is required when SNMPv3 private protocol is specified'
            )

        verrors.check()

        if not any([new['v3'], new['v3_username']]) and old['v3_username']:
            # v3 is disabled: Are we asked to delete the v3 user?
            await self.middleware.call('snmp.delete_snmp_user', old['v3_username'])
            new = self._reset_v3_settings(new)

        await self._update_service(old, new)

        # Manage update to SNMP v3 user
        if new['v3']:
            # v3 is enabled: Are there _any_ changes in the v3_* settings?
            new_set = set({k: v for k, v in new.items() if k.startswith('v3_')}.items())
            old_set = set({k: v for k, v in old.items() if k.startswith('v3_')}.items())
            v3_diffs = new_set ^ old_set
            if any(v3_diffs):
                await self.middleware.call('snmp.init_v3_user')

        return await self.config()


class SNMPServicePortDelegate(ServicePortDelegate):

    name = 'snmp'
    namespace = 'snmp'
    title = 'SNMP Service'

    async def get_ports_bound_on_wildcards(self):
        return [160, 161]


async def setup(middleware):
    await middleware.call('snmp.init_v3_user')
    await middleware.call('port.register_attachment_delegate', SNMPServicePortDelegate(middleware))
