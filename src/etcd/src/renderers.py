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
        self.config = context.configstore

    def get_template_context(self):
        return {
            "disclaimer": TemplateFunctions.disclaimer,
            "config": self.config,
            "dispatcher": self.context.client,
            "ds": self.context.datastore
        }

    def render_template(self, path):
        tmpl = Template(filename=path)
        return tmpl.render(**self.get_template_context())



class PythonRenderer(object):
    def __init__(self, context):
        self.context = context


class ShellTemplateRenderer(object):
    def __init__(self, context):
        self.context = context