#+
# Copyright 2015 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import random
import string
import mach
from utils import fail


def random_str():
    return ''.join(random.sample((string.ascii_uppercase+string.digits), 8))


def main():
    # Bind to service port
    server_port = mach.BootstrapServer.lookup("org.freenas.test.mach.ipc-server")
    local_port = mach.Port()

    print 'Service port: {0}'.format(server_port)
    print 'Local port: {0}'.format(local_port)

    # Send a few messages
    for i in range(0, 100):
        msg = mach.Message()
        msg.bits = mach.make_msg_bits(
            mach.MessageType.MACH_MSG_TYPE_COPY_SEND,
            mach.MessageType.MACH_MSG_TYPE_MAKE_SEND
        )

        msg.body = bytearray(random_str())
        local_port.send(server_port, msg)
        reply = local_port.receive()
        print 'Received reply: {0}'.format(reply.body)
        if reply.body != msg.body:
            fail('Reply mismatch: {0} != {1}'.format(msg.body, reply.body))

    # Exit
    msg = mach.Message()
    msg.bits = mach.make_msg_bits(
        mach.MessageType.MACH_MSG_TYPE_COPY_SEND,
        mach.MessageType.MACH_MSG_TYPE_MAKE_SEND
    )

    msg.body = bytearray('EXIT')
    mach.null_port.send(server_port, msg)

if __name__ == '__main__':
    main()