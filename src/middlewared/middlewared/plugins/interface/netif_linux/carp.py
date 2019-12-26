# -*- coding=utf-8 -*-
import logging

logger = logging.getLogger(__name__)

__all__ = ["CarpConfig", "CarpMixin"]


class CarpConfig:
    def __init__(self, *args, **kwargs):
        pass


class CarpMixin:
    @property
    def carp_config(self):
        return []

    @carp_config.setter
    def carp_config(self, carp_config):
        pass
