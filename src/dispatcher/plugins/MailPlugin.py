#
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
import errno
from email.mime.text import MIMEText

from dispatcher.rpc import (
    RpcException, SchemaHelper as h, accepts, description, returns
)
from lib.system import SubprocessException, system
from task import Provider, Task


@description("Provides Information about the mail configuration")
class MailProvider(Provider):

    @returns(h.ref('mail'))
    def query(self):
        mailobj = {}
        for key in self.dispatcher.rpc.schema_definitions['mail'][
            'properties'
        ].keys():
            mailobj[key] = self.dispatcher.configstore.get(
                'mail.{0}'.format(key)
            )
        return mailobj

    @accepts(h.ref('mail-message'))
    def send(self, email):
        msg = MIMEText(email.get('message'))
        msg['From'] = email.get('from')
        msg['To'] = email.get('to')
        msg['Subject'] = email.get('subject')
        try:
            system('sendmail', '-t', '-oi', stdin=msg.as_string())
        except SubprocessException, err:
            raise RpcException(
                errno.EFAULT, 'Cannot send mail: {0}'.format(err.err)
            )


@accepts(h.ref('mail'))
class MailConfigureTask(Task):

    def verify(self, mail):
        return []

    def run(self, mail):
        for key in self.dispatcher.rpc.schema_definitions['mail'][
            'properties'
        ].keys():
            if key not in mail:
                continue
            self.dispatcher.configstore.set(
                'mail.{0}'.format(key), mail.get(key)
            )
        self.dispatcher.call_sync('etcd.generation.generate_group', 'mail')


def _init(dispatcher):

    dispatcher.register_schema_definition('mail', {
        'type': 'object',
        'properties': {
            'server': {'type': 'string'},
            'port': {'type': 'integer'},
            'auth': {'type': 'boolean'},
            'encryption': {
                'type': 'string',
                'enum': ['PLAIN', 'TLS', 'SSL'],
            },
            'user': {'type': ['string', 'null']},
            'pass': {'type': ['string', 'null']},
        }
    })

    dispatcher.register_schema_definition('mail-message', {
        'type': 'object',
        'properties': {
            'from': {'type': 'string'},
            'to': {'type': 'string'},
            'subject': {'type': 'string'},
            'message': {'type': 'string'},
        }
    })

    # Register providers
    dispatcher.register_provider('mail', MailProvider)

    # Register task handlers
    dispatcher.register_task_handler('mail.configure', MailConfigureTask)
