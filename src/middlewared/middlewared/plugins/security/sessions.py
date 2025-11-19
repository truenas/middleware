# API endpoint to access active sessions from the PAM_TRUENAS keyring
#
# pam_truenas tracks various user session info in per-user keyrings
# When the application calls pam_open_session() information about
# the session is inserted into the keyring, when pam_close_session()
# is called by the application, the information is removed.

from datetime import datetime

from middlewared.api.base import BaseModel, NonEmptyString
from middlewared.service import filterable_api_method, Service
from middlewared.utils.filter_list import filter_list
from truenas_pam_session import iterate_sessions

# Currently session info is private and consumed for STIG purposes but we can
# expose in future by moving APIs here to formal external definitions


class SecuritySessionEntry(BaseModel):
    session_uuid: NonEmptyString
    """ UUID for the PAM session """
    pid: int
    """ Process ID """
    sid: int
    """ Session ID """
    username: str
    """ Username for authenticated PAM session """
    uid: int
    """ User ID for user associated with username """
    gid: int
    """ Group ID for user associated with username """
    service: str
    """ PAM service name used for session """
    ruser: str
    """ PAM_RUSER set by the application """
    rhost: str
    """ PAM_RHOST set by the application """
    tty: str
    """ PAM_TTY set by the application """
    creation: datetime
    """ Session open timestamp """


def truenas_session_iterator():
    for session in iterate_sessions():
        yield {
            'session_uuid': str(session.session_id),
            'creation': session.creation,
            'pid': session.pid,
            'sid': session.sid,
            'username': session.username,
            'uid': session.uid,
            'gid': session.gid,
            'service': session.service,
            'ruser': session.ruser,
            'rhost': session.rhost,
            'tty': session.tty,
        }


class SystemSecurityInfoService(Service):

    class Config:
        namespace = 'system.security.sessions'
        cli_namespace = 'system.security.sessions'

    @filterable_api_method(item=SecuritySessionEntry, private=True)
    def query(self, filters, options):
        """ Query current open PAM sessions. This includes all services
        that use the PAM stack, so you'll see webshare sessions, FTP
        sessions, openssh sessions, etc. """
        return filter_list(truenas_session_iterator(), filters, options)
