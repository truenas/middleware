from dojango.forms.widgets import DojoWidgetMixin
from django.forms import widgets
from django.utils.safestring import mark_safe
from django.forms.util import flatatt
from django.utils.encoding import StrAndUnicode, force_unicode

class CronMultiple(DojoWidgetMixin, widgets.Widget):
    dojo_type = 'freeadmin.form.Cron'
    def render(self, name, value, attrs=None):
        if value is None: value = ''
        final_attrs = self.build_attrs(attrs, name=name)
        final_attrs['value'] = force_unicode(value)
        if value in ('*',''):
            final_attrs['typeChoice'] = "all"
        elif value.startswith('*/'):
            final_attrs['typeChoice'] = "every"
        else:
            final_attrs['typeChoice'] = "selected"
        return mark_safe(u'<div%s></div>' % (flatatt(final_attrs),))
