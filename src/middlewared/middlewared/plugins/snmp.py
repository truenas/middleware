import middlewared.sqlalchemy as sa
import subprocess
import os

from contextlib import suppress
from middlewared.api import api_method
from middlewared.api.current import (
    SNMPEntry,
    SNMPUpdateArgs, SNMPUpdateResult
)

from middlewared.common.ports import ServicePortDelegate
from middlewared.plugins.snmp_.utils_snmp_user import (
    SNMPSystem, _add_system_user,
    add_snmp_user, delete_snmp_user, get_users_cmd
)
from middlewared.service import private, SystemServiceService, ValidationErrors


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
        entry = SNMPEntry
        role_prefix = 'SYSTEM_GENERAL'

    @private
    def get_snmp_users(self):
        """
        NOTE: This should be called with SNMP running
        Use snmpwalk and the SNMP system user to get the list
        """
        # Make sure we have the SNMP system user
        if not SNMPSystem.SYSTEM_USER['key']:
            self.middleware.call_sync('snmp.init_v3_user')

        users = []
        if cmd := get_users_cmd():
            try:
                # This call will timeout if SNMP is not running
                res = subprocess.run(cmd, capture_output=True)
                users = [x.split()[-1].strip('\"') for x in res.stdout.decode().splitlines()]
            except Exception:
                self.logger.warning("Failed to list snmp v3 users")
        else:
            self.logger.warning("SNMP system user is not configured.  Stop and restart SNMP or reboot.")

        return users

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
    async def _is_snmp_running(self):
        """ Internal helper function for use by this module """
        current_state = await self.middleware.call(
            'service.query', [["service", "=", "snmp"]], {"select": ["state"]}
        )
        return current_state[0]['state'] == 'RUNNING'

    @private
    async def init_v3_user(self):
        """
        Purpose: Make sure we have configured the snmpAuthUser
        This will generate the SNMP system user and, if we needed, repair the v3 user
        This will start and stop SNMP as needed.
        NOTE: This will raise CallError if SNMP is unable to be started

        Process:
            1) Record current SNMP run state
            2) Stop SNMP and delete the private config file
            3) Start SNMP to regenerate a new config file without any v3 users
            4) Stop SNMP and add v3 user markers to the private config
            5) Start SNMP to integrate the v3 users
                - snmpd detects the 'markers', internally generates the user
                  and deletes the 'markers'.
            6) Restore SNMP to 'current' run state

        Process notes:
            - We delete the private config file to make sure we're starting with
              a pristine config file that contains no bogus user markers or other chaff.
        """
        config = await self.middleware.call('snmp.config')

        # 1) Record current SNMP run state
        snmp_service = await self.middleware.call("service.query", [("service", "=", "snmp")], {"get": True})

        # 2) Stop SNMP and delete the private config file
        await (await self.middleware.call("service.control", "STOP", "snmp")).wait(raise_error=True)
        with suppress(FileNotFoundError):
            await self.middleware.run_in_thread(os.remove, SNMPSystem.PRIV_CONF)

        # 3) Start SNMP to regenerate a new config file without any v3 users
        await (await self.middleware.call('service.control', 'START', 'snmp')).wait(raise_error=True)

        # 4) Stop SNMP and add v3 user markers to the private config
        await (await self.middleware.call("service.control", "STOP", "snmp")).wait(raise_error=True)
        await self.middleware.run_in_thread(_add_system_user)

        # if configured, add the v3 user
        if config['v3_username']:
            await self.middleware.run_in_thread(add_snmp_user, config)

        # 5) Start SNMP to integrate the v3 users
        await (await self.middleware.call('service.control', 'START', 'snmp')).wait(raise_error=True)

        # 6) Restore SNMP to 'current' run state
        if snmp_service['state'] == "STOPPED":
            await (await self.middleware.call("service.control", "STOP", "snmp")).wait(raise_error=True)

    @api_method(SNMPUpdateArgs, SNMPUpdateResult)
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
        # Make sure we have the SNMP system user
        if not SNMPSystem.SYSTEM_USER['key']:
            await self.init_v3_user()

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

        # To delete the v3 user:
        #   From the UI: In the following order, clear the username field, then uncheck the v3 checkbox
        #   From midclt: set {'v3': False, 'v3_username': ''}
        if not any([new['v3'], new['v3_username']]) and old['v3_username']:
            # v3 is disabled: Are we asked to delete the v3 user?
            # Process to delete the SNMPv3 user
            # 1) SNMP must be running
            # 2) Delete the user with the snmpusm shell command
            # 3) Clear the v3 settings in the config
            # 3) Restore SNMP run state
            snmp_service = await self.middleware.call("service.query", [("service", "=", "snmp")], {"get": True})
            await (await self.middleware.call('service.control', 'START', 'snmp')).wait(raise_error=True)
            try:
                await self.middleware.run_in_thread(delete_snmp_user, old['v3_username'])
            except Exception:
                verrors.add("Cannot delete user. Please stop and restart SNMP or reboot, then try again.")
            else:
                config_default = self.get_defaults()
                default_v3_config = {k: v for (k, v) in config_default.items() if k.startswith('v3')}
                new.update(default_v3_config)

            # Restore original SNMP state
            if 'STOPPED' in snmp_service['state']:
                await (await self.middleware.call('service.control', 'STOP', 'snmp')).wait(raise_error=True)

        await self._update_service(old, new)

        # Manage update to SNMP v3 user
        if new['v3']:
            # v3 is enabled: Are there _any_ changes in the v3_* settings?
            new_set = set({k: v for k, v in new.items() if k.startswith('v3_')}.items())
            old_set = set({k: v for k, v in old.items() if k.startswith('v3_')}.items())
            v3_diffs = new_set ^ old_set
            if any(v3_diffs):
                await self.init_v3_user()

        return await self.config()


class SNMPServicePortDelegate(ServicePortDelegate):

    name = 'snmp'
    namespace = 'snmp'
    title = 'SNMP Service'

    async def get_ports_bound_on_wildcards(self):
        return [160, 161]


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', SNMPServicePortDelegate(middleware))
