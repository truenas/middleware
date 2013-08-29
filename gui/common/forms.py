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
from dojango.forms import ModelForm as MF
from dojango.forms import Form as F


def mchoicefield(form, field, default):
    """
    Utility method to convert comma delimited field
    """
    if field in form.initial:
        cm = form.initial[field]
    else:
        cm = form.fields[field].initial
    if cm == '*':
        form.initial[field] = default
    elif ',' in cm:
        form.initial[field] = cm.split(',')


class AdvMixin(object):

    def __init__(self, *args, **kwargs):
        if not hasattr(self, 'advanced_fields'):
            self.advanced_fields = []
        super(AdvMixin, self).__init__(*args, **kwargs)

    def isAdvanced(self):
        return len(self.advanced_fields) > 0


class ModelForm(AdvMixin, MF):
    """
    We need to handle dynamic choices, mainly because of the FreeNAS_User,
    so we use a custom formfield with a _reroll method which is called
    on every form instantiation
    """
    def __init__(self, *args, **kwargs):
        self._fserrors = {}
        self._api = kwargs.pop('api_validation', False)
        super(ModelForm, self).__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if hasattr(field, "_reroll"):
                field._reroll()

    def as_table(self):
        """Returns this form rendered as HTML <tr>s -- excluding the
        <table></table>."""
        return self._html_output(
            normal_row=(u'<tr%(html_class_attr)s><th>%(label)s</th><td>'
                '%(errors)s%(field)s</td></tr>'),
            error_row=u'<tr><td colspan="2">%s</td></tr>',
            row_ender=u'</td></tr>',
            help_text_html=u'<br />%s',
            errors_on_separate_row=False)

    def delete(self, request=None, events=None):
        self.instance.delete()

    def is_valid(self, formsets=None):
        valid = super(ModelForm, self).is_valid()
        if valid is False:
            return valid
        if formsets is not None:
            for name, fs in formsets.items():
                methodname = "clean%s" % (name, )
                if hasattr(self, methodname):
                    valid &= getattr(self, methodname)(fs, fs.forms)
        if self._fserrors:
            if '__all__' not in self._errors:
                self._errors['__all__'] = self._fserrors
            else:
                self._errors['__all__'] += self._fserrors
        return valid

    def done(self, request, events):
        pass


class Form(AdvMixin, F):
    """
    We need to handle dynamic choices, mainly because of the FreeNAS_User,
    so we use a custom formfield with a _reroll method which is called
    on every form instantiation
    """
    def __init__(self, *args, **kwargs):
        self._api = kwargs.pop('api_validation', False)
        super(Form, self).__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if hasattr(field, "_reroll"):
                field._reroll()

    def as_table(self):
        """Returns this form rendered as HTML <tr>s -- excluding the
        <table></table>."""
        return self._html_output(
            normal_row=(u'<tr%(html_class_attr)s><th>%(label)s</th><td>'
                '%(errors)s%(field)s</td></tr>'),
            error_row=u'<tr><td colspan="2">%s</td></tr>',
            row_ender=u'</td></tr>',
            help_text_html=u'<br />%s',
            errors_on_separate_row=False)
