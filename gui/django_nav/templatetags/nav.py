import re

from django import template

from django_nav import nav_groups

register = template.Library()
keyword_value_pair_regex = re.compile("((\w+)\s*=\s*)?(((?P<quote>'|\")(.*?)(?P=quote))|([^\s='\"]*))(?=(\s|$))")

def next_bit_for(bits, key, if_none=None):
    try:
        return bits[bits.index(key)+1].strip('"').strip("'")
    except ValueError:
        return if_none

def args_parser(args_string):
    var_list = []
    key_var_map = {}
    args_string = args_string.strip()
    while True:
        match = keyword_value_pair_regex.match(args_string)
        if match is None:
            if args_string != '':
                var_list.append(args_string)
            break
        keyword = match.group(2)
        value = match.group(6)
        if value == None:
            value = match.group(7)

        if keyword is None and value == '':
            if args_string != '':
                var_list.append(args_string)
            break
        elif keyword is None:
            var_list.append(value)
        else:
            key_var_map[str(keyword)] = value
        args_string = args_string[len(match.group(0)):].strip()

    return var_list, key_var_map

def resolve(var, context):
    """Resolves a variable out of context if it's not in quotes"""
    return template.Variable(var).resolve(context)

class GetNavNode(template.Node):
    def __init__(self, nav_group, var_name, args, kwargs):
            self.nav_group = nav_group
            self.var_name = var_name
            self.args = args
            self.kwargs = kwargs
            self.context = {'request': ''}

    def render(self, context):
        self.context = context
        self.build_nav()
        return ''

    def build_nav(self):
        self.context[self.var_name] = []

        for nav in nav_groups[self.nav_group]:
            if self.args:
                nav.args = [resolve(a, self.context) for a in self.args]

            if self.kwargs:
                for key, value in self.kwargs.iteritems():
                    self.kwargs[key] = resolve(value, self.context)
                nav.kwargs = self.kwargs

            if self.check_conditional(nav):
                continue
            nav.option_list = self.build_options(nav.options)
            nav.active = False
            path = self.context['request'].path
            url = nav.get_absolute_url()
            nav.active = nav.active_if(url, path)

            self.context[self.var_name].append(
                template.loader.render_to_string(nav.template, {'nav': nav}))

    def build_options(self, nav_options):
        options = []
        for option in nav_options:
            #option = option()
            if self.args:
                option.args = self.args

            if self.kwargs:
                option.kwargs = self.kwargs

            if self.check_conditional(option):
                continue
            option.option_list = self.build_options(option.options)
            options.append(template.loader.render_to_string(option.template,
                                                            {'option': option}))

        return options

    def check_conditional(self, of):
        conditional = of.conditional.get('function')
        return conditional and not conditional(self.context,
                                           *of.conditional['args'],
                                           **of.conditional['kwargs'])

@register.tag
def get_nav(parser, token):
    """
    additional args/kwargs after the var_name are attached to each nav
    item in the group as their args/kwargs attributes which are used
    for the get_absolute_url
    {% get_nav "NAV GROUP" as "var_name" 1, 2, ..., kwarg=1, kwarg2=2, ... %}
    """
    bits = token.contents.split()
    args = {
        'nav_group': next_bit_for(bits, 'get_nav'),
        'var_name': next_bit_for(bits, 'as', 'tabs'),
    }
    args['args'], args['kwargs'] = args_parser(' '.join(bits[bits.index(args['var_name'])+1:]))

    return GetNavNode(**args)
