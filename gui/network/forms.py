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

import re

from django.utils.translation import ugettext as _

from freenasUI.common.forms import ModelForm
from freenasUI.middleware.notifier import notifier
from freenasUI.network import models
from freenasUI import choices
from dojango import forms

class InterfacesForm(ModelForm):
    class Meta:
        model = models.Interfaces 

    int_interface = forms.ChoiceField(label = "NIC")

    def __init__(self, *args, **kwargs):
        super(InterfacesForm, self).__init__(*args, **kwargs)
        self.fields['int_interface'].choices = choices.NICChoices()

    def save(self):
        # TODO: new IP address should be added in a side-by-side manner
        # or the interface wouldn't appear once IP was changed.
        retval = super(InterfacesForm, self).save()
        notifier().start("network")
        return retval

class GlobalConfigurationForm(ModelForm):
    class Meta:
        model = models.GlobalConfiguration
    def clean(self):
        cleaned_data = self.cleaned_data
        nameserver1 = cleaned_data.get("gc_nameserver1")
        nameserver2 = cleaned_data.get("gc_nameserver2")
        nameserver3 = cleaned_data.get("gc_nameserver3")
        if nameserver3 != "":
            if nameserver2 == "":
                msg = _(u"Must fill out nameserver 2 before "
                         "filling out nameserver 3")
                self._errors["gc_nameserver3"] = self.error_class([msg])
                msg = _(u"Required when using nameserver 3")
                self._errors["gc_nameserver2"] = self.error_class([msg])
                del cleaned_data["gc_nameserver2"]
            if nameserver1 == "":
                msg = _(u"Must fill out nameserver 1 before "
                         "filling out nameserver 3")
                self._errors["gc_nameserver3"] = self.error_class([msg])
                msg = _(u"Required when using nameserver 3")
                self._errors["gc_nameserver1"] = self.error_class([msg])
                del cleaned_data["gc_nameserver1"]
            if nameserver1 == "" or nameserver2 == "":
                del cleaned_data["gc_nameserver3"]
        elif nameserver2 != "":
            if nameserver1 == "":
                del cleaned_data["gc_nameserver2"]
                msg = _(u"Must fill out nameserver 1 before "
                         "filling out nameserver 2")
                self._errors["gc_nameserver2"] = self.error_class([msg])
                msg = _(u"Required when using nameserver 3")
                self._errors["gc_nameserver1"] = self.error_class([msg])
                del cleaned_data["gc_nameserver1"]
        return cleaned_data
    def save(self):
        # TODO: new IP address should be added in a side-by-side manner
        # or the interface wouldn't appear once IP was changed.
        retval = super(GlobalConfigurationForm, self).save()
        notifier().reload("networkgeneral")
        return retval

class VLANForm(ModelForm):
    vlan_pint = forms.ChoiceField(label = "Parent Interface")

    def __init__(self, *args, **kwargs):
        super(VLANForm, self).__init__(*args, **kwargs)
        self.fields['vlan_pint'].choices = list(choices.NICChoices(novlan = True))

    def clean_vlan_vint(self):
        name = self.cleaned_data['vlan_vint']
        if not re.match(r'vlan\d+', name):
            raise forms.ValidationError("The name must be vlanXX where "
                                        "XX is a integer")
        return name

    def clean_vlan_tag(self):
        tag = self.cleaned_data['vlan_tag']
        if  tag > 4095:
            raise forms.ValidationError("VLAN Tags are 1 - 4095 inclusive")
        return tag

    class Meta:
        model = models.VLAN 

    def save(self):
        retval = super(VLANForm, self).save()
        notifier().start("network")
        return retval

attrs_dict = { 'class': 'required' }

class LAGGInterfaceForm(forms.Form):
    lagg_protocol = forms.ChoiceField(choices=choices.LAGGType,
                          widget=forms.RadioSelect(attrs=attrs_dict))
    lagg_interfaces = forms.MultipleChoiceField(
                            widget=forms.SelectMultiple(attrs=attrs_dict),
                            label = _('Physical NICs in the LAGG')
                            )

    def __init__(self, *args, **kwargs):
        super(LAGGInterfaceForm, self).__init__(*args, **kwargs)
        self.fields['lagg_interfaces'].choices = list(choices.NICChoices(nolagg = True))


class LAGGInterfaceMemberForm(ModelForm):
    class Meta:
        model = models.LAGGInterfaceMembers
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
            self.fields['int_interface'] = (
                forms.CharField(label=self.fields['int_interface'].label,
                                initial = instance.int_interface,
                                widget = forms.TextInput(
                                attrs = { 'readonly' : True })))
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
        model = models.StaticRoute
    def save(self):
        retval = super(StaticRouteForm, self).save()
        notifier().start("routing")
        return retval
