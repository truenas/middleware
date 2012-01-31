#+
# Copyright 2010, 2012 iXsystems, Inc.
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
import types

from django.utils.translation import ugettext_lazy as _, ugettext as __, ungettext

from dojango import forms

class UnixPermissionWidget(widgets.MultiWidget):
    def __init__(self, attrs=None):

        widgets = [forms.widgets.CheckboxInput,] * 9
        super(UnixPermissionWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        rv = [False] * 9
        if value and type(value) in types.StringTypes:
            mode = int(value, 8)
            for i in xrange(len(rv)):
                rv[i] = bool(mode & pow(2, len(rv)-i-1))
        return rv

    def format_output(self, rendered_widgets):

        maprow = (
            __('Read'),
            __('Write'),
            __('Execute'),
        )

        mapcol = (
            __('Owner'),
            __('Group'),
            __('Other'),
        )

        html = """<table>
        <thead>
        <tr>
        <td></td>
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        </tr>
        </thead>
        <tbody>
        """ % (mapcol[:])

        for i, mode_type in enumerate(maprow):
            html += "<tr>"
            html += "<td>%s</td>" % (mode_type, )
            for j in xrange(len(mapcol)):
                html += '<td>%s</td>' % (rendered_widgets[j*3+i], )
            html += "</tr>"
        html += "</tbody></table>"

        return html

class UnixPermissionField(forms.MultiValueField):

    widget = UnixPermissionWidget()

    def __init__(self, *args, **kwargs):
        fields = [forms.BooleanField()] * 9
        super(UnixPermissionField, self).__init__(fields, *args, **kwargs)

    def compress(self, value):
        if value:
            owner = 0
            group = 0
            other = 0
            if value[0] == True:
                owner += 4
            if value[1] == True:
                owner += 2
            if value[2] == True:
                owner += 1
            if value[3] == True:
                group += 4
            if value[4] == True:
                group += 2
            if value[5] == True:
                group += 1
            if value[6] == True:
                other += 4
            if value[7] == True:
                other += 2
            if value[8] == True:
                other += 1

            return ''.join(map(str, [owner, group, other]))
        return None
