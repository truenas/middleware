#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################

from django.shortcuts import render_to_response
from django.template import RequestContext

from freenasUI.sharing.forms import * 

def home(request):

    variables = RequestContext(request, {
    'focused_tab' : 'sharing',
    })
    return render_to_response('sharing/index2.html', variables)

def windows(request):

    cifs_share_list = CIFS_Share.objects.select_related().all()

    variables = RequestContext(request, {
        'cifs_share_list': cifs_share_list,
    })
    return render_to_response('sharing/windows.html', variables)

def apple(request):

    afp_share_list = AFP_Share.objects.order_by("-id").values()

    variables = RequestContext(request, {
    'afp_share_list': afp_share_list,
    })
    return render_to_response('sharing/apple.html', variables)

def unix(request):

    nfs_share_list = NFS_Share.objects.select_related().all()

    variables = RequestContext(request, {
    'nfs_share_list': nfs_share_list,
    })
    return render_to_response('sharing/unix.html', variables)
