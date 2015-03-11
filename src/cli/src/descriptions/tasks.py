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


def get_username(context, uid):
    u = context.connection.call_sync('users.query', [('id', '=', uid)], {'single': True})
    return u['username'] if u else '<unknown>'

tasks = {
    'zfs.pool.scrub': (_("Scrub volume"), lambda c, a: _("Scrub volume {0}").format(a[0])),
    'service.manage': (_("Manage service"), lambda c, a: _("{0} service {1}".format(a[1].title(), a[0]))),
    'service.configure': (_("Update service configuration"), lambda c, a: _("Update configuration for service {0}".format(a[0]))),
    'users.create': (_("Create user"), lambda c, a: _("Create user".format(a[0]['username']))),
    'users.update': (_("Update user profile"), lambda c, a: _("Update user {0} profile".format(get_username(c, a[0])))),
    'groups.create': (_("Create group"), lambda c, a: _("Create group {0}".format(a[0]['name']))),
    'groups.update': (_("Update group"), lambda c, a: _("Update group {0}".format(a[0]))),
    'volume.create': (_("Create volume"), lambda c, a: _("Create volume {0}".format(a[0]['name']))),
    'volume.create_auto': (_("Create volume"), lambda c, a: _("Create volume {0}".format(a[0]))),
    'volume.destroy': (_("Destroy volume"), lambda c, a: _("Destroy volume {0}".format(a[0]))),
    'disk.format.gpt': (_("Format disk"), lambda c, a: _("Format disk {0}".format(a[0]))),
    'zfs.pool.create': (_("Create ZFS pool"), lambda c, a: _("Create ZFS pool {0}".format(a[0]))),
    'zfs.pool.destroy': (_("Destroy ZFS pool"), lambda c, a: _("Destroy ZFS pool {0}".format(a[0]))),
    'zfs.mount': (_("Mount ZFS dataset"), lambda c, a: _("Mount ZFS dataset {0}".format(a[0]))),
    'network.interface.configure': (_("Configure network interface"), lambda c, a: _("Configure network interface {0}".format(a[0]))),
    'network.interface.up': (_("Enable network interface"), lambda c, a: _("Enable network interface {0}".format(a[0]))),
    'network.interface.down': (_("Disable network interface"), lambda c, a: _("Disable network interface {0}".format(a[0])))
}


def translate(context, name, args=None):
    if name not in tasks.keys():
        return name

    first, second = tasks[name]

    if args is None:
        return first

    return second(context, args)

