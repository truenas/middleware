# -*- coding=utf-8 -*-
import logging
import os

from mako.lookup import TemplateLookup

logger = logging.getLogger(__name__)

__all__ = ["get_template"]

lookup = TemplateLookup(
    directories=[os.path.dirname(os.path.dirname(__file__))],
    module_directory="/tmp/mako",
)


def get_template(name):
    return lookup.get_template(name)
