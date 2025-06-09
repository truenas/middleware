import enum
import json
import subprocess
from typing import Literal
from pydantic import Field
from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import QueryFilters, QueryOptions

from middlewared.service import Service, private
from middlewared.plugins.smb import SMBCmd
from middlewared.service_exception import CallError
from middlewared.utils import filter_list


class InfoLevel(enum.Enum):
    AUTH_LOG = 'l'
    ALL = ''
    SESSIONS = 'p'
    SHARES = 'S'
    LOCKS = 'L'
    BYTERANGE = 'B'
    NOTIFICATIONS = 'N'


class SMBStatusOptions(BaseModel):
    verbose: bool = True
    fast: bool = False
    restrict_user: str = ''
    restrict_session: str = ''
    resolve_uids: bool = True


class SMBStatusArgs(BaseModel):
    info_level: Literal['ALL', 'SESSIONS', 'SHARES', 'LOCKS', 'BYTERANGE', 'NOTIFICATIONS'] = 'ALL'
    query_filters: QueryFilters = QueryFilters()
    query_options: QueryOptions = QueryOptions()
    status_options: SMBStatusOptions = Field(default_factory=SMBStatusOptions)


class SMBStatusResult(BaseModel):
    result: list[dict] | dict | int


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    # TODO - convert this method into properly documented public API
    @api_method(SMBStatusArgs, SMBStatusResult, private=True)
    def status(self, info_level, filters, options, status_options):
        """
        Returns SMB server status (sessions, open files, locks, notifications).

        `info_level` type of information requests. Defaults to ALL.

        `status_options` additional options to filter query results. Supported
        values are as follows: `verbose` gives more verbose status output
        `fast` causes smbstatus to not check if the status data is valid by
        checking if the processes that the status data refer to all still
        exist. This speeds up execution on busy systems and clusters but
        might display stale data of processes that died without cleaning up
        properly. `restrict_user` specifies the limits results to the specified
        user.

        This API endpoint also supports a legacy `info_level` AUTH_LOG that
        provides AUTHENTICATION events from the SMB audit log. Support for
        this information level will be removed in a future version.
        """
        lvl = InfoLevel[info_level]
        if lvl == InfoLevel.AUTH_LOG:
            return self.middleware.call_sync('audit.query', {
                'services': ['SMB'],
                'query-filters': filters + [['event', '=', 'AUTHENTICATION']],
                'query-options': options
            })

        """
        Apply some optimizations for case where filter is only asking
        for a specific uid or session id.
        """
        if len(filters) == 1:
            to_check = filters[0][:2]
            if to_check == ["uid", "="]:
                status_options['restrict_user'] = str(filters[0][2])
                filters = []

            elif to_check == ["session_id", "="]:
                status_options['restrict_session'] = str(filters[0][2])
                filters = []

        flags = '-j'
        flags = flags + lvl.value
        flags = flags + 'v' if status_options['verbose'] else flags
        flags = flags + 'f' if status_options['fast'] else flags

        statuscmd = [SMBCmd.STATUS.value, '-d' '0', flags]

        if status_options['restrict_user']:
            statuscmd.extend(['-U', status_options['restrict_user']])

        if status_options['restrict_session']:
            statuscmd.extend(['-s', status_options['restrict_session']])

        if status_options['resolve_uids']:
            statuscmd.append('--resolve-uids')

        smbstatus = subprocess.run(statuscmd, capture_output=True)

        if smbstatus.returncode != 0:
            raise CallError(f'Failed to retrieve SMB status: {smbstatus.stderr.decode().strip()}')

        json_status = json.loads(smbstatus.stdout.decode() or '{"sessions": {}}')

        if lvl == InfoLevel.SESSIONS:
            to_filter = list(json_status.get("sessions", {}).values())

        elif lvl == InfoLevel.LOCKS:
            to_filter = list(json_status.get("open_files", {}).values())

        elif lvl == InfoLevel.BYTERANGE:
            to_filter = list(json_status.get("byte_range_locks", {}).values())

        elif lvl == InfoLevel.NOTIFICATIONS:
            to_filter = list(json_status.get("notifies", {}).values())

        elif lvl == InfoLevel.SHARES:
            to_filter = list(json_status.get("tcons", {}).values())

        else:
            for tcon in json_status.get("tcons", {}).values():
                if not (session := json_status['sessions'].get(tcon['session_id'])):
                    continue

                if not session.get('share_connections'):
                    session['share_connections'] = [tcon]
                else:
                    session['share_connections'].append(tcon)

            to_filter = list(json_status['sessions'].values())

        return filter_list(to_filter, filters, options)

    @private
    def client_count(self):
        """
        Return currently connected clients count.
        """
        return self.status("SESSIONS", [], {"count": True}, {"fast": True})
