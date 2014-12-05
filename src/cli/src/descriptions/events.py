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


import gettext

t = gettext.translation('freenas-cli', fallback=True)
_ = t.ugettext


def task_updated(args):
    return ''


events = {
    'server.client_connected': (_("Client connected"), lambda a: _("Client connected from {0}").format(a['address'])),
    'server.client_logged': (_("User logged in"), lambda a: _("User {0} logged in").format(a['username'])),
    'server.service_logged': (_("Service logged in"), lambda a: _("Service {0} logged in").format(a['name'])),
    'server.client_disconnected': (_("Client disconnected"), lambda a: _("Client {0} disconnected").format(a['address'])),
    'task.created': (_("Task created"), lambda a: _("Task {0} created").format(a['id'])),
    'task.updated': (_("Task updated"), task_updated),
}


def translate(name, args=None):
    if name not in events.keys():
        return name

    first, second = events[name]

    if args is None:
        return first

    return second(args)
