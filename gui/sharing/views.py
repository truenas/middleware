#+
# Copyright 2010 iXsystems, Inc.
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

from django.shortcuts import render

from freenasUI.freeadmin.apppool import appPool
from freenasUI.sharing import models


def home(request):

    view = appPool.hook_app_index('sharing', request)
    if view:
        return view[0]

    return render(request, 'sharing/index.html', {
        'focus_form': request.GET.get('tab', ''),
    })


def windows(request):
    cifs_share_list = models.CIFS_Share.objects.select_related().all()
    return render(request, 'sharing/windows.html', {
        'cifs_share_list': cifs_share_list,
        'model': models.CIFS_Share,
    })


def apple(request):
    afp_share_list = models.AFP_Share.objects.order_by("-id").all()
    return render(request, 'sharing/apple.html', {
        'afp_share_list': afp_share_list,
        'model': models.AFP_Share,
    })


def unix(request):
    nfs_share_list = models.NFS_Share.objects.select_related().all()
    return render(request, 'sharing/unix.html', {
        'nfs_share_list': nfs_share_list,
        'model': models.NFS_Share,
    })
