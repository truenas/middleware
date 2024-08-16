# This file provides constants and methods related to general middleware limits.
# Currently tests are provided in ./src/middlewared/middlewared/pytest/unit/utils/test_limits.py

import enum

from aiohttp.http_websocket import WSCloseCode
from truenas_api_client import json as ejson


# WARNING: below methods must _not_ be audited. c.f. comment in parse_message() below
MSG_SIZE_EXTENDED_METHODS = set((
    'filesystem.file_receive',
))


class MsgSizeLimit(enum.IntEnum):
    UNAUTHENTICATED = 8192  # maximum size of message processed from unauthenticated session
    AUTHENTICATED = 65536  # maximum size of message processed from authentication session
    EXTENDED = 2097152  # maximum size of message that sends a file


class MsgSizeError(Exception):
    def __init__(self, limit, datalen, method_name=None):
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

    def __str__(self):
        return self.errmsg


def parse_message(authenticated: bool, msg_data: str) -> dict:
    """
    Check given message to determine whether it exceeds size limits

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

    message = ejson.loads(msg_data)

    if (method := message.get('method')) in MSG_SIZE_EXTENDED_METHODS:
        return message

    if datalen > MsgSizeLimit.AUTHENTICATED:
        raise MsgSizeError(MsgSizeLimit.AUTHENTICATED, datalen, method)

    return message
