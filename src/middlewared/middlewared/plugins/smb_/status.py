import enum
import json
import subprocess

from middlewared.api import api_method
from middlewared.api.current import SMBStatusArgs, SMBStatusResult
from middlewared.plugins.smb import SMBCmd
from middlewared.service import Service, private
from middlewared.service_exception import CallError
from middlewared.utils.filter_list import filter_list


class InfoLevel(enum.Enum):
    AUTH_LOG = 'l'
    ALL = ''
    SESSIONS = 'p'
    SHARES = 'S'
    LOCKS = 'L'
    BYTERANGE = 'B'
    NOTIFICATIONS = 'N'


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @api_method(SMBStatusArgs, SMBStatusResult, roles=['SHARING_SMB_READ'])
    def status(self, info_level, filters, options, status_options):
        """Returns SMB server status (sessions, open files, locks, notifications)."""
        # First handle AUTH_LOG
        lvl = InfoLevel[info_level]
        if lvl is InfoLevel.AUTH_LOG:
            return self.middleware.call_sync('audit.query', {
                'services': ['SMB'],
                'query-filters': filters + [['event', '=', 'AUTHENTICATION']],
                'query-options': options
            })

        restrict_user = status_options['restrict_user']
        restrict_session = status_options['restrict_session']
        # Apply some optimizations for case where filter is only asking for a specific uid or session id.
        if len(filters) == 1:
            f = filters[0]
            match f[:2]:
                case ['uid', '=']:
                    restrict_user = str(f[2])
                    filters = []
                case ['session_id', '=']:
                    restrict_session = str(f[2])
                    filters = []

        # Build command
        flags = '-j' + lvl.value
        if status_options['verbose']:
            flags += 'v'
        if status_options['fast']:
            flags += 'f'

        statuscmd = [SMBCmd.STATUS.value, '-d' '0', flags]

        if restrict_user:
            statuscmd.extend(['-U', restrict_user])

        if restrict_session:
            statuscmd.extend(['-s', restrict_session])

        if status_options['resolve_uids']:
            statuscmd.append('--resolve-uids')

        # Run command
        smbstatus = subprocess.run(statuscmd, capture_output=True)

        if smbstatus.returncode != 0:
            raise CallError(f'Failed to retrieve SMB status: {smbstatus.stderr.decode().strip()}')

        # Parse and return output
        json_status = json.loads(smbstatus.stdout.decode() or '{"sessions": {}}')

        match lvl:
            case InfoLevel.SESSIONS:
                key = 'sessions'
            case InfoLevel.LOCKS:
                key = 'open_files'
            case InfoLevel.BYTERANGE:
                key = 'byte_range_locks'
            case InfoLevel.NOTIFICATIONS:
                key = 'notifies'
            case InfoLevel.SHARES:
                key = 'tcons'
            case _:
                key = 'sessions'
                for tcon in json_status.get('tcons', {}).values():
                    if not (session := json_status[key].get(tcon['session_id'])):
                        continue

                    if session.get('share_connections'):
                        session['share_connections'].append(tcon)
                    else:
                        session['share_connections'] = [tcon]

        to_filter = list(json_status.get(key, {}).values())
        return filter_list(to_filter, filters, options)

    @private
    def client_count(self):
        """
        Return currently connected clients count.
        """
        return self.status('SESSIONS', [], {'count': True}, {'fast': True})
