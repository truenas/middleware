import re
from django import template
from django import forms
from django.forms.forms import BoundField
from django.utils.html import conditional_escape
from django.utils.encoding import force_unicode

register = template.Library()

class FormRender(template.Node):
    def __init__(self, arg):
        self.arg = arg
    def render(self, context):
        form = context[self.arg]
        model = form._meta.model

        new_fields = form.fields.keys()
        output, hidden_fields, composed = [], [], {}

        top_errors = form.non_field_errors()
        if top_errors:
            output.append("<tr><td colspan=\"2\">%s</td></tr>" % force_unicode(top_errors))

        for label, fields in model._admin.composed_fields:
            for field in fields[1:]:
                new_fields.remove(field)
            composed[fields[0]] = (label, fields)

        for field in new_fields:
            if composed.has_key(field):
                label, fields = composed.get(field)
                html = u"""<tr><th><label>%s</label></th><td>""" % (label)
                for field in fields:
                    bf = BoundField(form, form.fields[field], field)
                    bf_errors = form.error_class([conditional_escape(error) for error in bf.errors])
                    html += unicode(bf_errors) + unicode(bf) 
                    #new_fields.remove(field)
                html += u"</td></tr>"    
                output.append(html)
            else:
                bf = BoundField(form, form.fields[field], field)
                bf_errors = form.error_class([conditional_escape(error) for error in bf.errors])
                if bf.is_hidden:
                    hidden_fields.append(unicode(bf))
                else:
                    html = u"""<tr><th>%s</th><td>%s%s</td></tr>""" % (bf.label_tag(), bf_errors, bf)
                    output.append(html)

        if hidden_fields:
            str_hidden = u''.join(hidden_fields)
            output.append(str_hidden)

        return ''.join(output)


@register.tag(name="admin_form")
def do_admin_form(parser, token):
    # This version uses a regular expression to parse tag contents.
    try:
        # Splitting by None == splitting by spaces.
        tag_name, arg = token.contents.split(None, 1)
        print tag_name, arg
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires arguments" % token.contents.split()[0])

    #if not (format_string[0] == format_string[-1] and format_string[0] in ('"', "'")):
    #    raise template.TemplateSyntaxError("%r tag's argument should be in quotes" % tag_name)
    return FormRender(arg)
