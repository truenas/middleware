__author__ = 'jceel'

from mako.template import Template
from datastore.config import ConfigStore


class TemplateFunctions:
    @staticmethod
    def disclaimer(comment_style='#'):
        return "{} WARNING: This file was auto-generated".format(comment_style)


class MakoTemplateRenderer(object):
    def __init__(self, context):
        self.context = context
        self.config = ConfigStore(context.datastore)

    def get_template_context(self):
        return {
            "disclaimer": TemplateFunctions.disclaimer,
            "config": self.config
        }

    def render_template(self, path):
        tmpl = Template(filename=path)
        return tmpl.render(**self.get_template_context())


class ShellTemplateRenderer(object):
    def __init__(self, context):
        self.context = context