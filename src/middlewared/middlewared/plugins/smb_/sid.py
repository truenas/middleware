import subprocess

from middlewared.api.current import ServiceOptions
from middlewared.service import Service, private
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils.sid import random_sid

from .constants import SMBCmd


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @private
    def local_server_sid(self):
        if (db_sid := self.middleware.call_sync('datastore.config', 'services.cifs')['cifs_SID']):
            return db_sid

        new_sid = random_sid()
        if self.middleware.call_sync('failover.is_single_master_node'):
            self.middleware.call_sync('datastore.update', 'services.cifs', 1, {'cifs_SID': new_sid})

        return new_sid

    @private
    def set_system_sid(self):
        server_sid = self.local_server_sid()
        netbiosname = self.middleware.call_sync('smb.config')['netbiosname']

        sid_read_failed = False
        try:
            current_sid = self.middleware.call_sync('directoryservices.secrets.domain_sid', netbiosname)
        except (FileNotFoundError, MatchNotFound):
            # secrets.tdb does not exist yet or holds no SID for our netbios name
            current_sid = None
        except Exception:
            # An unexpected read failure is not the same as a genuinely-absent SID: we
            # cannot prove the SID was unchanged, so record that the read failed and let
            # the restart decision below err on the side of restarting winbindd.
            self.logger.warning(
                '%s: failed to read current local server SID from secrets', netbiosname, exc_info=True
            )
            current_sid = None
            sid_read_failed = True

        if current_sid == server_sid:
            return

        setsid = subprocess.run([
            SMBCmd.NET.value, '-d', '0',
            'setlocalsid', server_sid,
        ], capture_output=True, check=False)

        if setsid.returncode != 0:
            raise CallError(f'setlocalsid failed: {setsid.stderr.decode()}')

        if (current_sid is None and not sid_read_failed) or not self.call_sync2(self.s.service.started, 'idmap'):
            # Skip the restart when we know there was no prior SID (a fresh secrets.tdb has
            # nothing stale for winbindd to rebuild) or when winbindd isn't running. When the
            # read failed instead, current_sid is None but sid_read_failed is True, so we fall
            # through and restart -- leaving winbindd on a possibly-stale SID is the worse risk.
            return

        # winbindd captures the local SAM domain SID from secrets.tdb when it starts.
        # Changing the SID under a running winbindd leaves its domain list referencing
        # a SID that the SAMR/passdb layer no longer accepts, and group token expansion
        # fails with NT_STATUS_NO_SUCH_DOMAIN until winbindd is restarted.
        self.logger.warning(
            '%s: local server SID changed from %s to %s while winbindd was running. Restarting '
            'winbindd to rebuild its view of the local SAM domain.',
            netbiosname, current_sid, server_sid
        )
        self.call_sync2(
            self.s.service.control, 'RESTART', 'idmap', ServiceOptions(silent=False, ha_propagate=False)
        ).wait_sync(raise_error=True)
