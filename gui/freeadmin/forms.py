#+
# Copyright 2011 iXsystems
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
import re

from django.forms.widgets import Widget
from django.forms.util import flatatt
from django.utils.safestring import mark_safe
from django.utils.encoding import StrAndUnicode, force_unicode
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from dojango.forms.widgets import DojoWidgetMixin
from dojango import forms
from dojango.forms import widgets
from freenasUI.common.freenasldap import FreeNAS_Users, FreeNAS_User, \
                                         FreeNAS_Groups, FreeNAS_Group
from account.forms import FilteredSelectJSON

class CronMultiple(DojoWidgetMixin, Widget):
    dojo_type = 'freeadmin.form.Cron'
    def render(self, name, value, attrs=None):
        if value is None: value = ''
        final_attrs = self.build_attrs(attrs, name=name)
        final_attrs['value'] = force_unicode(value)
        if value.startswith('*/'):
            final_attrs['typeChoice'] = "every"
        elif re.search(r'^[0-9].*',value):
            final_attrs['typeChoice'] = "selected"
        return mark_safe(u'<div%s></div>' % (flatatt(final_attrs),))

class DirectoryBrowser(widgets.Widget):
    def render(self, name, value, attrs=None):
        context = dict(name=name, value=value, attrs=attrs)
        return mark_safe(render_to_string('freeadmin/directory_browser.html', context))

class UserField(forms.ChoiceField):
    widget = widgets.Select()

    def _reroll(self):
        if len(FreeNAS_Users()) > 500:
            if self.initial:
                self.choices = ((self.initial, self.initial),)
            self.widget = FilteredSelectJSON(url=("account_bsduser_json",))
        else:
            ulist = []
            if not self.required:
                ulist.append(('-----', 'N/A'))
            [ulist.append((x.bsdusr_username, x.bsdusr_username))
                                                      for x in FreeNAS_Users()
                                                     ]
                
            self.widget = widgets.FilteringSelect()
            self.choices = ulist


    def clean(self, user):
        if not self.required and user in ('-----',''):
            return None
        if FreeNAS_User(user) == None:
            raise forms.ValidationError(_("The user %s is not valid.") % user)
        return user

class GroupField(forms.ChoiceField):
    widget = widgets.Select()

    def _reroll(self):
        if len(FreeNAS_Groups()) > 500:
            if self.initial:
                self.choices = ((self.initial, self.initial),)
            self.widget = FilteredSelectJSON(url=("account_bsdgroup_json",))
        else:
            glist = []
            if not self.required:
                glist.append(('-----', 'N/A'))
            [glist.append((x.bsdgrp_group, x.bsdgrp_group))
                                                      for x in FreeNAS_Groups()
                                                     ]
            self.widget = widgets.FilteringSelect()
            self.choices = glist

    def clean(self, group):
        if not self.required and group in ('-----',''):
            return None
        if FreeNAS_Group(group) == None:
            raise forms.ValidationError(_("The group %s is not valid.") % group)
        return group

class PathField(forms.CharField):
    widget = DirectoryBrowser()
