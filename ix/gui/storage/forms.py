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

from django import forms
from django.shortcuts import render_to_response
from freenasUI.storage.models import *
from freenasUI.middleware.notifier import notifier
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from dojango.forms.models import ModelForm
from dojango.forms import fields, widgets
from dojango.forms.fields import BooleanField
from freenasUI.contrib.ext_formwizard import FormWizard

attrs_dict = { 'class': 'required' }

# Step 1.  Creation of volumes manually is not supported.
class VolumeWizard_VolumeNameTypeForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(VolumeWizard_VolumeNameTypeForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = [ (x, x) for x in self._populate_disklist() ]
    def _populate_disklist(self):
        from os import popen
        import re

        disklist = []

        # Grab disk list
        pipe = popen("/sbin/sysctl -n kern.disks")
        disklist = pipe.read().strip().split(' ')

        # Exclude the root device
        rootdev = popen("""glabel status | grep `mount | awk '$3 == "/" {print $1}' | sed -e 's/\/dev\///'` | awk '{print $3}'""").read().strip()
        rootdev_base = re.search('[a-z/]*[0-9]*', rootdev)
        if rootdev_base != None:
            disklist = [ x for x in disklist if x != rootdev_base.group(0) ]

        # Exclude what's already added
        known_disks = set([ x['disk_disks'] for x in Disk.objects.all().values('disk_disks') ])
        disklist = set(disklist).difference(known_disks)
        return disklist
    volume_name = forms.CharField(max_length = 30)
    volume_fstype = forms.ChoiceField(choices = ((x, x) for x in ('ufs', 'zfs')), widget=forms.RadioSelect(attrs=attrs_dict))
    volume_disks = forms.MultipleChoiceField(choices=(), widget=forms.SelectMultiple(attrs=attrs_dict))

# Step 2.  Creation of volumes manually is not supported.
# This step only show up when more than 1 disks is being chosen.
class VolumeWizard_DiskGroupTypeForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(VolumeWizard_DiskGroupTypeForm, self).__init__(*args, **kwargs)
        grouptype_choices = ( ('mirror', 'mirror'), )
        fstype = kwargs['initial']['fstype']
        disks =  kwargs['initial']['disks']
        if fstype == "ufs":
            grouptype_choices += (
                ('stripe', 'stripe'),
                )
            if len(disks) >= 3:
                grouptype_choices += (
                    ('raid3', 'RAID-3'),
                    ('raid5' , 'RAID-5'),
                    )
        elif fstype == "zfs":
            grouptype_choices += (
                ('', 'stripe'),
                )
            if len(disks) >= 3:
                grouptype_choices += ( ('raidz', 'RAID-Z'), )
            if len(disks) >= 4:
                grouptype_choices += ( ('raidz2', 'RAID-Z2'), )
            # Not yet
            #if len(disks) >= 5:
            #    grouptype_choices += ( ('raidz3', 'RAID-Z3'), )
        self.fields['group_type'].choices = grouptype_choices
    group_type = forms.ChoiceField(choices=(), widget=forms.RadioSelect(attrs=attrs_dict))

# Step 3.  Just show a page with "Finish".
class VolumeFinalizeForm(forms.Form):
    pass

#=================================

# A partial form for editing disk.
# we only show disk_name (used as GPT label), disk_disks
# (device name), and disk_group (which group this disk belongs
# to), but don't allow editing.
class DiskFormPartial(ModelForm):
    class Meta:
        model = Disk
        exclude = ('disk_name', 'disk_disks', 'disk_group')

#=================================
# Finally, the wizard.

class VolumeWizard(FormWizard):
    def process_step(self, request, form, step):
        if step==0:
            disks = form.cleaned_data['volume_disks']
            if self.step <= step:
                if (len(disks) < 2):
	            self.form_list.remove(VolumeWizard_DiskGroupTypeForm)
                else:
                    self.initial[1] = {'fstype': form.cleaned_data['volume_fstype'], 'disks': disks}
            elif len(disks) < 2:
	        self.form_list.remove(VolumeWizard_DiskGroupTypeForm)
    def get_template(self, step):
        return 'storage/wizard.html'
    def done(self, request, form_list):
        # Construct and fill forms into database.
	#
	volume_name = form_list[0].cleaned_data['volume_name']
	volume_fstype = form_list[0].cleaned_data['volume_fstype']
        disk_list = form_list[0].cleaned_data['volume_disks']

        if (len(disk_list) < 2):
            group_type = ''
        else:
            group_type = form_list[1].cleaned_data['group_type']

        volume = Volume(vol_name = volume_name, vol_fstype = volume_fstype)
        volume.save()

        mp = MountPoint(mp_volume=volume, mp_path='/mnt/' + volume_name, mp_options='rw')
        mp.save()

        grp = DiskGroup(group_name= volume_name + group_type, group_type = group_type, group_volume = volume)
        grp.save()

        for diskname in disk_list:
            diskobj = Disk(disk_name = diskname, disk_disks = diskname, disk_description = "Member of " + volume_name + " " + group_type, disk_group = grp)
            diskobj.save()

	notifier().init("volume", volume.id)
        return HttpResponseRedirect('/')

# Wrapper for the wizard.  Without the wrapper we end up
# messing with data in the global urls object which makes
# it impossible to re-enter the wizard for the second time.
def VolumeWizard_wrapper(request, *args, **kwargs):
	return VolumeWizard([VolumeWizard_VolumeNameTypeForm, VolumeWizard_DiskGroupTypeForm, VolumeFinalizeForm])(request, *args, **kwargs)

