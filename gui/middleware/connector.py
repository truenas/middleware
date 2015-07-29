#-
# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

import logging
import time
import socket
from dispatcher.client import Client, ClientError


logger = logging.getLogger('middleware.dispatcher')
connection = None


def on_error(error):
    if error in (ClientError.CONNECTION_CLOSED, ClientError.LOGOUT):
        logger.warning('Conenction lost, trying to reconnect')
        while True:
            try:
                connection.connect('127.0.0.1')
                connection.login_service('django')
                logger.warning('Reconnected successfully')
                return
            except socket.error, err:
                logger.warning('Reconnect failed: {0}: retrying in one second'.format(str(err)))
                time.sleep(1)


def create_connection():
    global connection
    try:
        connection = Client()
        connection.on_error(on_error)
        connection.connect('127.0.0.1')
        connection.login_service('django')
    except socket.error, err:
        from notifier import MiddlewareError
        raise MiddlewareError('Cannot connect to dispatcher: {0}'.format(str(err)))


create_connection()
