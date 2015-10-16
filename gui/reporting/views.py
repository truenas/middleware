# Copyright 2012 iXsystems, Inc.
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
import json
import logging

from django.shortcuts import render

from freenasUI.freeadmin.apppool import appPool
from freenasUI.reporting import graphs

log = logging.getLogger('reporting.views')


def plugin2graphs(name):

    rv = []
    if name in graphs.name2plugin:
        ins = graphs.name2plugin[name]()
        ids = ins.get_identifiers()
        if ids is not None:
            if len(ids) > 0:
                for ident in ids:
                    ins.identifier = ident
                    rv.append({
                        'plugin': ins.name,
                        'identifier': ident,
                        'sources': json.dumps(ins.get_sources()),
                        'vertical_label': ins.vertical_label,
                        'title': ins.get_title(),
                    })
        else:
            rv.append({
                'plugin': ins.name,
                'sources': json.dumps(ins.get_sources()),
                'vertical_label': ins.vertical_label,
                'title': ins.get_title(),
            })

    return rv


def index(request):

    view = appPool.hook_app_index('reporting', request)
    view = filter(None, view)
    if view:
        return view[0]

    return render(request, "reporting/index.html")


def generic_graphs(request, names=None):

    if names is None:
        names = []

    graphs = []
    for name in names:
        graphs.extend(plugin2graphs(name))

    return render(request, 'reporting/graphs.html', {
        'graphs': graphs,
    })
