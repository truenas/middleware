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
import re

from django.db import models

from south.modelsinspector import add_introspection_rules

add_introspection_rules([], ["^(freenasUI\.)?freeadmin\.models\.UserField"])
add_introspection_rules([], ["^(freenasUI\.)?freeadmin\.models\.GroupField"])
add_introspection_rules([], ["^(freenasUI\.)?freeadmin\.models\.PathField"])
add_introspection_rules([], ["^(freenasUI\.)?freeadmin\.models\.MACField"])
add_introspection_rules(
    [], ["^(freenasUI\.)?freeadmin\.models\.Network4Field"]
)
add_introspection_rules(
    [], ["^(freenasUI\.)?freeadmin\.models\.Network6Field"]
)


class UserField(models.CharField):
    def __init__(self, *args, **kwargs):
        self._exclude = kwargs.pop('exclude', [])
        kwargs['max_length'] = kwargs.get('max_length', 120)
        super(UserField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        #FIXME: Move to top (causes cycle-dependency)
        from freenasUI.freeadmin.forms import UserField as UF
        defaults = {'form_class': UF, 'exclude': self._exclude}
        kwargs.update(defaults)
        return super(UserField, self).formfield(**kwargs)


class GroupField(models.CharField):
    def formfield(self, **kwargs):
        #FIXME: Move to top (causes cycle-dependency)
        from freenasUI.freeadmin.forms import GroupField as GF
        defaults = {'form_class': GF}
        kwargs.update(defaults)
        return super(GroupField, self).formfield(**kwargs)


class PathField(models.CharField):

    description = "A generic path chooser"

    def __init__(self, *args, **kwargs):
        self.abspath = kwargs.pop("abspath", True)
        self.includes = kwargs.pop("includes", [])
        self.dirsonly = kwargs.pop("dirsonly", False)
        self.filesonly = kwargs.pop("filesonly", False)
        kwargs['max_length'] = 255
        if kwargs.get('blank', False):
            kwargs['null'] = True
        super(PathField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        #FIXME: Move to top (causes cycle-dependency)
        from freenasUI.freeadmin.forms import PathField as PF
        defaults = {
            'form_class': PF,
            'abspath': self.abspath,
            'includes': self.includes,
            'dirsonly': self.dirsonly,
            'filesonly': self.filesonly,
        }
        kwargs.update(defaults)
        return super(PathField, self).formfield(**kwargs)


class MACField(models.Field):
    empty_strings_allowed = False
    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 17
        super(MACField, self).__init__(*args, **kwargs)

    def get_internal_type(self):
        return "CharField"

    def formfield(self, **kwargs):
        from freenasUI.freeadmin.forms import MACField as MF
        defaults = {'form_class': MF}
        defaults.update(kwargs)
        return super(MACField, self).formfield(**defaults)

    def to_python(self, value):
        if value:
            return value.replace(':', '')
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        if value:
            return re.sub(r'(?P<du>[0-9A-F]{2})(?!$)', '\g<du>:', value)
        return value


class Network4Field(models.CharField):

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 18  # 255.255.255.255/32
        super(Network4Field, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        #FIXME: Move to top (causes cycle-dependency)
        from freenasUI.freeadmin.forms import Network4Field as NF
        defaults = {'form_class': NF}
        kwargs.update(defaults)
        return super(Network4Field, self).formfield(**kwargs)


class Network6Field(models.CharField):

    def __init__(self, *args, **kwargs):
        # ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128
        kwargs['max_length'] = 43
        super(Network6Field, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        #FIXME: Move to top (causes cycle-dependency)
        from freenasUI.freeadmin.forms import Network6Field as NF
        defaults = {'form_class': NF}
        kwargs.update(defaults)
        return super(Network6Field, self).formfield(**kwargs)
