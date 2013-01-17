#+
# Copyright 2013 iXsystems, Inc.
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
import logging   

from django.http import HttpResponse 
from django.shortcuts import render
from django.utils import simplejson
from django.utils.translation import ugettext as _

from freenasUI.middleware.notifier import notifier
from freenasUI.jails import forms
from freenasUI.jails import models

log = logging.getLogger("jails.views")

def jails_home(request):

    try:
        jailsconf = models.JailsConfiguration.objects.order_by("-id")[0].id
    except IndexError:
        jailsconf = models.JailsConfiguration.objects.create().id

    return render(request, 'jails/index.html', {
        'focused_form': request.GET.get('tab', 'jails'),
         'jailsconf': jailsconf
    })

def jail_auto(request, id):
    log.debug("XXX: jail_auto() id = %d" % id)
    pass

def jail_checkup(request, id):
    log.debug("XXX: jail_checkup() id = %d" % id)
    pass

def jail_details(request, id):
    log.debug("XXX: jail_details() id = %d" % id)
    pass

def jail_export(request, id):
    log.debug("XXX: jail_export() id = %d" % id)
    pass

def jail_import(request, id):
    log.debug("XXX: jail_import() id = %d" % id)
    pass

def jail_options(request, id):
    log.debug("XXX: jail_options() id = %d" % id)
    pass

def jail_pkgs(request, id):
    log.debug("XXX: jail_pkgs() id = %d" % id)
    pass

def jail_pbis(request, id):
    log.debug("XXX: jail_pbis() id = %d" % id)
    pass

def jail_start(request, id):
    log.debug("XXX: jail_start() id = %d" % id)
    pass

def jail_stop(request, id):
    log.debug("XXX: jail_stop() id = %d" % id)
    pass

def jail_zfsmksnap(request, id):
    log.debug("XXX: jail_zfsmksnap() id = %d" % id)
    pass

def jail_zfslistclone(request, id):
    log.debug("XXX: jail_zfslistclone() id = %d" % id)
    pass

def jail_zfslistsnap(request, id):
    log.debug("XXX: jail_zfslistsnap() id = %d" % id)
    pass

def jail_zfsclonesnap(request, id):
    log.debug("XXX: jail_zfsclonesnap() id = %d" % id)
    pass

def jail_zfscronsnap(request, id):
    log.debug("XXX: jail_zfscronsnap() id = %d" % id)
    pass

def jail_zfsrevertsnap(request, id):
    log.debug("XXX: jail_zfsrevertsnap() id = %d" % id)
    pass

def jail_zfsrmclonesnap(request, id):
    log.debug("XXX: jail_zfsrmclonesnap() id = %d" % id)
    pass

def jail_zfsrmsnap(request, id):
    log.debug("XXX: jail_zfsrmsnap() id = %d" % id)
    pass
