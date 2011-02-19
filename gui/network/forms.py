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
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode 
from dojango.forms import fields, widgets 
from dojango.forms.fields import BooleanField 
from django.utils.translation import ugettext as _
from dojango import forms

from freenasUI.common.forms import ModelForm
from freenasUI.common.forms import Form
from freenasUI.middleware.notifier import notifier
#TODO: do not import *
from freenasUI.network.models import *                         

class InterfacesForm(ModelForm):
    class Meta:
        model = Interfaces 
    def save(self):
        # TODO: new IP address should be added in a side-by-side manner
	    # or the interface wouldn't appear once IP was changed.
        retval = super(InterfacesForm, self).save()
        notifier().start("network")
        return retval

class GlobalConfigurationForm(ModelForm):
    class Meta:
        model = GlobalConfiguration
    def clean(self):
        cleaned_data = self.cleaned_data
        nameserver1 = cleaned_data.get("gc_nameserver1")
        nameserver2 = cleaned_data.get("gc_nameserver2")
        nameserver3 = cleaned_data.get("gc_nameserver3")
        if nameserver3 != "":
            if nameserver2 == "":
                msg = _(u"Must fill out nameserver 2 before filling out nameserver 3")
                self._errors["gc_nameserver3"] = self.error_class([msg])
                msg = _(u"Required when using nameserver 3")
                self._errors["gc_nameserver2"] = self.error_class([msg])
                del cleaned_data["gc_nameserver2"]
            if nameserver1 == "":
                msg = _(u"Must fill out nameserver 1 before filling out nameserver 3")
                self._errors["gc_nameserver3"] = self.error_class([msg])
                msg = _(u"Required when using nameserver 3")
                self._errors["gc_nameserver1"] = self.error_class([msg])
                del cleaned_data["gc_nameserver1"]
            if nameserver1 == "" or nameserver2 == "":
                del cleaned_data["gc_nameserver3"]
        elif nameserver2 != "":
            if nameserver1 == "":
                del cleaned_data["gc_nameserver2"]
                msg = _(u"Must fill out nameserver 1 before filling out nameserver 2")
                self._errors["gc_nameserver2"] = self.error_class([msg])
                msg = _(u"Required when using nameserver 3")
                self._errors["gc_nameserver1"] = self.error_class([msg])
                del cleaned_data["gc_nameserver1"]
        return cleaned_data
    def save(self):
        # TODO: new IP address should be added in a side-by-side manner
	    # or the interface wouldn't appear once IP was changed.
        super(GlobalConfigurationForm, self).save()
        notifier().reload("networkgeneral")

class VLANForm(ModelForm):
    class Meta:
        model = VLAN 

attrs_dict = { 'class': 'required' }

class LAGGInterfaceForm(forms.Form):
    lagg_protocol = forms.ChoiceField(choices=LAGGType, \
            widget=forms.RadioSelect(attrs=attrs_dict))
    lagg_interfaces = forms.MultipleChoiceField(choices=list(NICChoices(nolagg=True)), \
            widget=forms.SelectMultiple(attrs=attrs_dict), \
            label = _('Physical NICs in the LAGG'))

    def __init__(self, *args, **kwargs):
        super(LAGGInterfaceForm, self).__init__(*args, **kwargs)
        choices = self.fields['lagg_interfaces'].choices
        nics = [value for value, label in choices]

        physnics = LAGGInterfaceMembers.objects.filter(lagg_physnic__in=nics).values('lagg_physnic')
        for each in physnics:
            choices.remove( (each['lagg_physnic'], each['lagg_physnic']) )

        self.fields['lagg_interfaces'].choices = choices

    def clean_lagg_interfaces(self):

        ifaces = self.cleaned_data['lagg_interfaces']
        physnics = LAGGInterfaceMembers.objects.filter(lagg_physnic__in=ifaces).values_list('lagg_physnic')
        if len(physnics) > 0:
            if len(physnics) == 1:
                raise forms.ValidationError(_("The interfaces %s is already registered for another LAGG Interface") % ( physnics[0] ) )
            else:
                raise forms.ValidationError(_("The interfaces (%s) are already registered for another LAGG Interface") % ( ','.join([v[0] for v in physnics]) ) )
        return self.cleaned_data['lagg_interfaces']

class LAGGInterfaceMemberForm(ModelForm):
    class Meta:
        model = LAGGInterfaceMembers
    def __init__(self, *args, **kwargs):
        super(LAGGInterfaceMemberForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.id:
            self.fields['lagg_interfacegroup'].widget.attrs['readonly'] = True
            self.fields['lagg_physnic'].widget.attrs['readonly'] = True
    def clean_lagg_interfacegroup(self):
        return self.instance.lagg_interfacegroup
    def clean_lagg_physnic(self):
        return self.instance.lagg_physnic

class InterfaceEditForm(InterfacesForm):
    def __init__(self, *args, **kwargs):
        super(InterfaceEditForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.id:
            self.fields['int_interface'] = forms.CharField(initial = instance.int_interface, widget = forms.TextInput(attrs = { 'readonly' : True }))
    def clean(self):
        super(InterfaceEditForm, self).clean()
        if 'int_interface' in self._errors:
            del self._errors['int_interface']
        self.cleaned_data['int_interface'] = self.instance.int_interface
        return self.cleaned_data
    def clean_int_interface(self):
        return self.instance.int_interface

class StaticRouteForm(ModelForm):
    class Meta:
        model = StaticRoute
    def save(self):
        super(StaticRouteForm, self).save()
        notifier().start("routing")
