# -*- coding=utf-8 -*-
import logging
import os

from mako.lookup import TemplateLookup
from mako.template import Template

logger = logging.getLogger(__name__)

__all__ = ["get_template"]

lookup = TemplateLookup(
    directories=[os.path.dirname(os.path.dirname(__file__))],
    module_directory="/run/mako",
)


def get_template(name: str) -> Template:
    return lookup.get_template(name)
