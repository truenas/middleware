from middlewared.schema import Bool, Dict, Ref, Str
from middlewared.service import Service, accepts
from middlewared.plugins.smb import SMBCmd
from middlewared.utils import filter_list

import enum
import json
import subprocess
import time


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

    @accepts(
        Str('info_level', enum=[x.name for x in InfoLevel], default=InfoLevel.ALL.name),
        Ref('query-filters'),
        Ref('query-options'),
        Dict('status_options',
             Bool('verbose', default=True),
             Bool('fast', default=False),
             Str('restrict_user', default='')
             )
    )
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
        """

        if InfoLevel[info_level] == InfoLevel.AUTH_LOG:
            ret = []
            try:
                with open("/var/log/samba4/auth_audit.log", "r") as f:
                    for e in f:
                        entry = json.loads(e.strip())
                        ts, extra = entry['timestamp'].split('.', 1)
                        # add timezone info
                        ts += extra[6:]
                        usec = extra[:6]
                        tv_sec = time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%S%z"))
                        timestamp_tval = {
                            "tv_sec": tv_sec,
                            "tv_usec": int(usec)
                        }
                        entry['timestamp_tval'] = timestamp_tval
                        ret.append(entry)

            except FileNotFoundError:
                self.logger.warning("SMB auth audit log does not exist "
                                    "this is expected if users have never "
                                    "authenticated to this server.")
                return ret

            return filter_list(ret, filters, options)

        flags = '-j'
        flags = flags + InfoLevel[info_level].value
        flags = flags + 'v' if status_options['verbose'] else flags
        flags = flags + 'f' if status_options['fast'] else flags

        statuscmd = [SMBCmd.STATUS.value, '-d' '0', flags]

        if status_options['restrict_user']:
            statuscmd.extend(['-U', status_options['restrict_user']])

        smbstatus = subprocess.run(statuscmd, capture_output=True)
        if smbstatus.returncode != 0:
            self.logger.debug('smbstatus [{%s}] failed with error: ({%s})',
                              flags, smbstatus.stderr.decode().strip())

        return filter_list(json.loads(smbstatus.stdout.decode()), filters, options)
