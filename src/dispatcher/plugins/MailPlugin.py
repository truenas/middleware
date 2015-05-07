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

from task import Provider
from dispatcher.rpc import (
    SchemaHelper as h, accepts, description, returns
)


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

    @accepts(h.ref('mail'))
    def update(self, mail):
        for key in self.dispatcher.rpc.schema_definitions['mail'][
            'properties'
        ].keys():
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
            'encryption': {'type': 'string'},
            'user': {'type': ['string', 'null']},
            'pass': {'type': ['string', 'null']},
        }
    })

    dispatcher.register_provider('mail', MailProvider)
