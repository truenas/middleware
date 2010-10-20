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
from freenasUI.services.models import *                         
from freenasUI.middleware.notifier import notifier
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode 
from dojango.forms.models import ModelForm as ModelForm
from dojango.forms import fields, widgets 
from dojango.forms.fields import BooleanField 

""" Services """

class servicesForm(ModelForm):
    class Meta:
        model = services

class CIFSForm(ModelForm):
    class Meta:
        model = CIFS
    def save(self):
        super(CIFSForm, self).save()
        notifier().reload("cifs")

class AFPForm(ModelForm):
    class Meta:
        model = AFP
    def save(self):
        super(AFPForm, self).save()
        notifier().restart("afp")

class NFSForm(ModelForm):
    class Meta:
        model = NFS
    def save(self):
        super(NFSForm, self).save()
        notifier().restart("nfs")

class FTPForm(ModelForm):
    def save(self):
        super(FTPForm, self).save()
        notifier().reload("ftp")
    class Meta:
        model = FTP 

class TFTPForm(ModelForm):
    def save(self):
        super(TFTPForm, self).save()
        notifier().reload("tftp")
    class Meta:
        model = TFTP 

class SSHForm(ModelForm):
    def save(self):
        super(SSHForm, self).save()
        notifier().reload("ssh")
    class Meta:
        model = SSH 

class rsyncjobForm(ModelForm):
    class Meta:
        model = rsyncjob

class UnisonForm(ModelForm):
    class Meta:
        model = Unison

class iSCSITargetForm(ModelForm):
    class Meta:
        model = iSCSITarget

class DynamicDNSForm(ModelForm):
    class Meta:
        model = DynamicDNS

class SNMPForm(ModelForm):
    class Meta:
        model = SNMP

class UPSForm(ModelForm):
    class Meta:
        model = UPS

class WebserverForm(ModelForm):
    class Meta:
        model = Webserver

class BitTorrentForm(ModelForm):
    class Meta:
        model = BitTorrent



class ActiveDirectoryForm(ModelForm):
    class Meta:
        model = ActiveDirectory

class LDAPForm(ModelForm):
    class Meta:
        model = LDAP

