# This file provides constants and methods related to general middleware limits.
# Currently tests are provided in ./src/middlewared/middlewared/pytest/unit/utils/test_limits.py

import enum

from typing import Any

from aiohttp.http_websocket import WSCloseCode
from truenas_api_client import json as ejson


# WARNING: below methods must _not_ be audited. c.f. comment in parse_message() below
MSG_SIZE_EXTENDED_METHODS = frozenset({
    'filesystem.file_receive',
    'failover.datastore.sql',
})


class MsgSizeLimit(enum.IntEnum):
    UNAUTHENTICATED = 8192  # maximum size of message processed from unauthenticated session
    AUTHENTICATED = 65536  # maximum size of message processed from authentication session
    EXTENDED = 2097152  # maximum size of message that sends a file


class MsgSizeError(Exception):
    def __init__(self, limit: MsgSizeLimit, datalen: int, method_name: str | None = None) -> None:
        self.limit = limit
        self.datalen = datalen
        self.errmsg = f'Message length [{self.datalen}] exceeded maximum size of {self.limit}'
        self.method_name = method_name or ''
        if limit is MsgSizeLimit.UNAUTHENTICATED:
            # This preserves legacy server behavior
            self.ws_close_code = WSCloseCode.INVALID_TEXT
            self.ws_errmsg = 'Anonymous connection max message length is 8 kB'
        else:
            self.ws_close_code = WSCloseCode.MESSAGE_TOO_BIG
            self.ws_errmsg = 'Max message length is 64 kB'

    def __str__(self) -> str:
        return self.errmsg


def parse_message(authenticated: bool, msg_data: str) -> dict[str, Any]:
    """
    Parses the JSON message and ensures that it is a dict, and it does not exceed size limits.

    WARNING: RFC5424 (syslog) specifies that SDATA of message should never
    exceed 64 KiB. The default syslog-ng configuration will not parse messages
    larger than this, hence, going above this value can potentially break
    auditing (either locally or sending to remote syslog server).

    The exception to this is for particular whitelisted methods (for example
    filesystem.file_receive) that must process very large amounts of data and
    are not audited

    parameters:
        authenticated - whether session is authenticated
        msg_data - data sent by client

    returns:
        JSON loads output of msg_data (dictionary)

    raises:
        JSONDecodeError (subclass of ValueError)
        MsgSizeError
    """
    datalen = len(msg_data)

    if not authenticated and datalen > MsgSizeLimit.UNAUTHENTICATED.value:
        raise MsgSizeError(MsgSizeLimit.UNAUTHENTICATED, datalen)

    if datalen > MsgSizeLimit.EXTENDED.value:
        raise MsgSizeError(MsgSizeLimit.EXTENDED, datalen)

    message: dict[str, Any] = ejson.loads(msg_data)

    try:
        method = message.get('method')
    except Exception:
        if isinstance(message, list):
            raise ValueError('Batch messages are not supported at this time')

        raise ValueError('Invalid Message Format')

    if method in MSG_SIZE_EXTENDED_METHODS:
        return message

    if datalen > MsgSizeLimit.AUTHENTICATED:
        raise MsgSizeError(MsgSizeLimit.AUTHENTICATED, datalen, method)

    return message
