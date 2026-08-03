# API endpoint to access active sessions from the PAM_TRUENAS keyring
#
# pam_truenas tracks various user session info in per-user keyrings
# When the application calls pam_open_session() information about
# the session is inserted into the keyring, when pam_close_session()
# is called by the application, the information is removed.

from collections.abc import Generator
from datetime import datetime
from typing import Any

import truenas_keyring
from truenas_pam_session import iterate_sessions

from middlewared.api.base import BaseModel, NonEmptyString
from middlewared.api.current import QueryOptions
from middlewared.service import Service, filterable_api_method, periodic
from middlewared.utils.filter_list import filter_list

# The kernel expires the uid=0 persistent keyring after
# kernel.keys.persistent_keyring_expiry seconds of non-use (3 days by default)
# and reaps everything linked under it, including the PAM_TRUENAS keyring that
# holds our session records. Every keyctl_get_persistent() resets that timer,
# which authentication performs, so this only matters on an appliance where
# nobody has authenticated for the whole window. Touch it well inside the
# window so an idle system does not silently lose its open session records.
KEYRING_KEEPALIVE_INTERVAL = 86400

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


def truenas_session_iterator() -> Generator[SecuritySessionEntry]:
    for session in iterate_sessions():
        yield SecuritySessionEntry(
            session_uuid=str(session.session_id),
            creation=session.creation,
            pid=session.pid,
            sid=session.sid,
            username=session.username,
            uid=session.uid,
            gid=session.gid,
            service=session.service,
            ruser=session.ruser,
            rhost=session.rhost,
            tty=session.tty,
        )


class SystemSecuritySessionsService(Service):

    class Config:
        namespace = 'system.security.sessions'
        private = True

    @filterable_api_method(item=SecuritySessionEntry, private=True, check_annotations=True)
    def query(
        self, filters: list[Any], options: QueryOptions
    ) -> list[SecuritySessionEntry] | SecuritySessionEntry | int:
        """ Query current open PAM sessions. This includes all services
        that use the PAM stack, so you'll see webshare sessions, FTP
        sessions, openssh sessions, etc. """
        return filter_list(truenas_session_iterator(), filters, options, SecuritySessionEntry)

    @periodic(interval=KEYRING_KEEPALIVE_INTERVAL)
    def keyring_keepalive(self) -> None:
        """ Reset the expiry timer on the uid=0 persistent keyring.

        get_persistent_keyring() gets or creates the keyring rather than
        searching within it, so this succeeds before anyone has authenticated
        and does not depend on PAM_TRUENAS existing yet. """
        truenas_keyring.get_persistent_keyring()
