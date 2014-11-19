#+
# Copyright 2014 iXsystems, Inc.
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


from texttable import Texttable
from namespace import Namespace, Command, IndexCommand, description


@description("Lists system services")
class ListUsersCommand(Command):
    def run(self, context, args):
        users = context.connection.call_sync('accounts.query_users')
        table = Texttable()
        table.set_deco(Texttable.HEADER | Texttable.VLINES | Texttable.BORDER)
        table.header(['Username', 'Full name', 'UID', 'Group', 'Shell', 'Home directory'])

        for u in users:
            table.add_row([u['username'], u['full_name'], u['id'], u['group'], u['shell'], u['home']])

        print table.draw()


@description("Lists system services")
class UserSetCommand(Command):
    def __init__(self, name):
        super(UserSetCommand, self).__init__()
        self.name = name

    def run(self, context, args):
        pass


@description("Lists system services")
class UserShowCommand(Command):
    def __init__(self, name):
        super(UserShowCommand, self).__init__()
        self.name = name

    def run(self, context, args):
        pass


@description("Lists system services")
class UserDeleteCommand(Command):
    def __init__(self, name):
        super(UserDeleteCommand, self).__init__()
        self.name = name

    def run(self, context, args):
        pass


class UserNamespace(Namespace):
    def __init__(self, context, name):
        super(UserNamespace, self).__init__()
        self.context = context
        self.name = name
        self.description = 'User {0}'.format(name)

    def commands(self):
        return {
            '?': IndexCommand(self),
            'set': UserSetCommand(self.name),
            'show': UserShowCommand(self.name),
            'delete': UserDeleteCommand(self.name)
        }


@description("Service namespace")
class AccountNamespace(Namespace):
    def __init__(self, context):
        super(AccountNamespace, self).__init__()
        self.context = context

    def commands(self):
        return {
            '?': IndexCommand(self),
            'list': ListUsersCommand()
        }

    def namespaces(self):
        result = {}
        users = self.context.connection.call_sync('accounts.query_users')

        for i in map(lambda u: u['username'], users):
            result[i] = UserNamespace(self.context, i)

        return result


def _init(context):
    context.attach_namespace('/account', AccountNamespace(context))