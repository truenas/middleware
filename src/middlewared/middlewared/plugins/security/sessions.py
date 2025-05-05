from datetime import datetime

from middlewared.api.base import BaseModel, NonEmptyString
from middlewared.service import filterable_api_method, Service
from middlewared.utils.account.utmp import utmp_query

from typing import Literal

# Currently utmp info is private and consumed for STIG purposes but we can
# expose in future by moving APIs here to formal external definitions


class SecuritySessionUtmpExitStatus(BaseModel):
    e_termination: int
    """ Process termination status """
    e_exit: int
    """ Process exit status """


class AccountPasswdEntry(BaseModel):
    pw_name: NonEmptyString
    pw_uid: int
    pw_gid: int
    pw_gecos: str
    pw_dir: str
    pw_shell: str
    source: Literal['FILES', 'SSS', 'WINBIND']
    """ Name of the NSS backend providing the passwd entry. This can be used to identify
    whether the account is local or provided by a directory service. """


class SecuritySessionEntry(BaseModel):
    ut_type_str: Literal['USER_PROCESS']
    """ The type of utmp record in string form. Currently we're only exposing USER_PROCESS
    but if we need to we can expand to also include LOGIN_PROCESS, DEAD_PROCESS, etc. """
    ut_type: int
    """ utmp record type. Corresponds with PyUtmpType IntEnum in utils/account/utmp.py """
    ut_pid: int
    """ Process ID of the login process """
    ut_line: NonEmptyString
    """ Device name of the tty with the prefix "/dev" removed """
    ut_id: str
    """ Terminal name suffix. """
    ut_user: NonEmptyString | None
    """ Username. Note that utmp only has a 32 byte buffer for usernames and so
    directory services names may be truncated. See notes on passwd below"""
    ut_host: NonEmptyString | None
    """ Hostname for the remote login. Note that utmp only has a 256 byte buffer for hostname field. """
    ut_addr: NonEmptyString | None
    """ IP address of remote host """
    ut_exit: SecuritySessionUtmpExitStatus | None
    """ Exit status for DEAD_PROCESS. Since we're not exposing those currently, will always be None """
    ut_session: int
    """ Session ID (getsid(2)) """
    ut_tv: datetime
    """ Time the entry was made """
    loginuid: int | None
    """ Login UID for process specified by ut_pid. Will be None if the process is defunct or
    if it has never properly been set """
    passwd: AccountPasswdEntry | None
    """ Passwd entry for the user. This is provided so that there's a robust mechanism for identifying
    the user account associated with a utmp entry. We can't entirely rely on ut_user because it may be
    truncated, which can result in non-unique entries for AD domains. """


class SystemSecurityInfoService(Service):

    class Config:
        namespace = 'system.security.sessions'
        cli_namespace = 'system.security.sessions'

    @filterable_api_method(item=SecuritySessionEntry, private=True)
    def query(self, filters, options):
        """Query current entries in utmp. This gets populated by processes performing
        normal login methods."""

        # See man(5) utmp. File can contain types that aren't particularly relevant
        filters.append(['ut_type_str', '=', 'USER_PROCESS'])
        return utmp_query(filters, options)
