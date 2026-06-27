from contextlib import suppress
import os
import subprocess
from typing import Any

from middlewared.api.current import QueryOptions, SNMPEntry, SNMPUpdate
from middlewared.plugins.snmp_.utils_snmp_user import (
    SNMPSystem,
    _add_system_user,
    add_snmp_user,
    delete_snmp_user,
    get_users_cmd,
)
from middlewared.service import SystemServicePart, ValidationErrors
import middlewared.sqlalchemy as sa


class SNMPModel(sa.Model):
    __tablename__ = "services_snmp"

    id = sa.Column(sa.Integer(), primary_key=True)
    snmp_location = sa.Column(sa.String(255))
    snmp_contact = sa.Column(sa.String(120))
    snmp_traps = sa.Column(sa.Boolean(), default=False)
    snmp_v3 = sa.Column(sa.Boolean(), default=False)
    snmp_community = sa.Column(sa.String(120), default="public")
    snmp_v3_username = sa.Column(sa.String(20))
    snmp_v3_authtype = sa.Column(sa.String(3), default="SHA")
    snmp_v3_password = sa.Column(sa.EncryptedText())
    snmp_v3_privproto = sa.Column(sa.String(3), nullable=True)
    snmp_v3_privpassphrase = sa.Column(sa.EncryptedText(), nullable=True)
    snmp_options = sa.Column(sa.Text())
    snmp_loglevel = sa.Column(sa.Integer(), default=3)
    snmp_zilstat = sa.Column(sa.Boolean(), default=False)


def snmp_model_defaults() -> dict[str, Any]:
    """Default config values pulled from the SQLAlchemy model, with nullable strings fixed up."""
    prefix = SNMPServicePart._datastore_prefix
    defaults: dict[str, Any] = {}
    for attrib in SNMPModel.__dict__.keys():
        if not attrib.startswith(prefix):
            continue
        column = getattr(SNMPModel, attrib)
        try:
            val = column.default.arg
        except AttributeError:
            val = "" if not column.nullable else None
        if not callable(val):
            defaults[attrib[len(prefix) :]] = val
    return defaults


class SNMPServicePart(SystemServicePart[SNMPEntry]):
    _datastore = "services.snmp"
    _datastore_prefix = "snmp_"
    _entry = SNMPEntry
    _service = "snmp"
    _service_verb = "restart"

    def get_snmp_users(self) -> list[str]:
        """
        NOTE: This should be called with SNMP running
        Use snmpwalk and the SNMP system user to get the list
        """
        # Make sure we have the SNMP system user
        if not SNMPSystem.SYSTEM_USER["key"]:
            self.run_coroutine(self.init_v3_user())

        users: list[str] = []
        if cmd := get_users_cmd():
            try:
                # This call will timeout if SNMP is not running
                res = subprocess.run(cmd, capture_output=True)
                users = [x.split()[-1].strip('"') for x in res.stdout.decode().splitlines()]
            except Exception:
                self.logger.warning("Failed to list snmp v3 users")
        else:
            self.logger.warning("SNMP system user is not configured.  Stop and restart SNMP or reboot.")

        return users

    async def init_v3_user(self) -> None:
        """
        Make sure we have configured the snmpAuthUser. This generates the SNMP system user and, if
        needed, repairs the v3 user, starting and stopping SNMP as required.

        The private config file is deleted first so we start from a pristine state with no bogus user
        markers. SNMP is then started to regenerate it, stopped to write the v3 user markers, and
        started again so snmpd integrates the users and removes the markers. Finally the original run
        state is restored.

        Raises CallError if SNMP is unable to be started.
        """
        config = await self.config()

        snmp_service = await self.call2(self.s.service.query, [("service", "=", "snmp")], QueryOptions(get=True))

        await (await self.call2(self.s.service.control, "STOP", "snmp")).wait(raise_error=True)
        with suppress(FileNotFoundError):
            await self.to_thread(os.remove, SNMPSystem.PRIV_CONF)

        await (await self.call2(self.s.service.control, "START", "snmp")).wait(raise_error=True)

        await (await self.call2(self.s.service.control, "STOP", "snmp")).wait(raise_error=True)
        await self.to_thread(_add_system_user)

        if config.v3_username:
            await self.to_thread(add_snmp_user, config.model_dump(context={"expose_secrets": True}))

        await (await self.call2(self.s.service.control, "START", "snmp")).wait(raise_error=True)

        if snmp_service["state"] == "STOPPED":
            await (await self.call2(self.s.service.control, "STOP", "snmp")).wait(raise_error=True)

    async def do_update(self, data: SNMPUpdate) -> SNMPEntry:
        # Make sure we have the SNMP system user
        if not SNMPSystem.SYSTEM_USER["key"]:
            await self.init_v3_user()

        old = await self.config()
        new = old.updated(data)

        verrors = ValidationErrors()

        # If not v3, then must have a community 'passcode'
        if not new.v3 and not new.community:
            verrors.add("snmp_update.community", "This field is required when SNMPv3 is disabled")

        # If v3, then must supply a username, authtype and password
        if new.v3:
            if not new.v3_username:
                verrors.add("snmp_update.v3_username", "This field is required when SNMPv3 is enabled")
            if not new.v3_authtype:
                verrors.add("snmp_update.v3_authtype", "This field is required when SNMPv3 is enabled")
            if not new.v3_password.get_secret_value():
                verrors.add("snmp_update.v3_password", "This field is required when SNMPv3 is enabled")

        # Get the above fixed first
        verrors.check()

        v3_password = new.v3_password.get_secret_value()
        if v3_password and len(v3_password) < 8:
            verrors.add("snmp_update.v3_password", "Password must contain at least 8 characters")

        if new.v3_privproto and not new.v3_privpassphrase.get_secret_value():
            verrors.add(
                "snmp_update.v3_privpassphrase", "This field is required when SNMPv3 private protocol is specified"
            )

        verrors.check()

        new_payload = new.model_dump(context={"expose_secrets": True})

        # To delete the v3 user:
        #   From the UI: In the following order, clear the username field, then uncheck the v3 checkbox
        #   From midclt: set {'v3': False, 'v3_username': ''}
        if not any([new.v3, new.v3_username]) and old.v3_username:
            # v3 is disabled and we're asked to delete the v3 user. SNMP must be running to delete the
            # user with snmpusm; we then clear the v3 settings and restore the original SNMP run state.
            snmp_service = await self.call2(self.s.service.query, [("service", "=", "snmp")], QueryOptions(get=True))
            await (await self.call2(self.s.service.control, "START", "snmp")).wait(raise_error=True)
            try:
                await self.to_thread(delete_snmp_user, old.v3_username)
            except Exception:
                self.logger.warning(
                    "snmp: failed to delete v3 user; stop and restart SNMP or reboot, then try again", exc_info=True
                )
            else:
                default_v3_config = {k: v for k, v in snmp_model_defaults().items() if k.startswith("v3")}
                new_payload.update(default_v3_config)

            # Restore original SNMP state
            if "STOPPED" in snmp_service["state"]:
                await (await self.call2(self.s.service.control, "STOP", "snmp")).wait(raise_error=True)

        update = {k: v for k, v in new_payload.items() if k != "id"}
        await self._update_service(old.id, update)

        # Manage update to SNMP v3 user
        if new_payload["v3"]:
            # v3 is enabled: re-init the user if any of the v3_* settings changed
            old_payload = old.model_dump(context={"expose_secrets": True})
            new_v3 = {k: v for k, v in new_payload.items() if k.startswith("v3_")}
            old_v3 = {k: v for k, v in old_payload.items() if k.startswith("v3_")}
            if set(new_v3.items()) ^ set(old_v3.items()):
                await self.init_v3_user()

        return await self.config()
