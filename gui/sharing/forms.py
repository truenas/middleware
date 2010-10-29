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

from django.forms import ModelForm                             
from django.shortcuts import render_to_response                
from freenasUI.sharing.models import *                         
from freenasUI.middleware.notifier import notifier
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode 
from dojango.forms.models import ModelForm as ModelForm
from dojango.forms import fields, widgets 
from dojango.forms.fields import BooleanField 

""" Shares """
class MountPointForm(ModelForm):
    class Meta:
        model = MountPoint

class CIFS_ShareForm(ModelForm):
    class Meta:
        model = CIFS_Share 
    def save(self):
        super(CIFS_ShareForm, self).save()
        notifier().reload("smbd")

class AFP_ShareForm(ModelForm):
    class Meta:
        model = AFP_Share 
    def save(self):
        super(AFP_ShareForm, self).save()
        notifier().reload("afp")

class NFS_ShareForm(ModelForm):
    class Meta:
        model = NFS_Share 
    def save(self):
        super(NFS_ShareForm, self).save()
        notifier().reload("nfs")

