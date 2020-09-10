# -*- coding=utf-8 -*-
__all__ = ['VrrpMixin']


class VrrpMixin:

    def __init__(self):
        self.data = None

    @property
    def vrrp_config(self):

        try:
            return self.data
        except AttributeError:
            # Interface class doesn't initialize
            # this class on inheritance so return None
            # until this attribute is explicitly configured
            return None

    @vrrp_config.setter
    def vrrp_config(self, data):
        """
        Keepalived (VRRP daemon) on SCALE actually adds/deletes
        the VIP from the interface as needed depending on whether
        or not the controller is in the MASTER or BACKUP state.

        So this function simply gets set to whatever is sent to it
        in the `interface/configure.py` plugin. This mixin is used
        so that interfaces on SCALE can have a "vrrp_config" property
        to match as close as possible to how freeBSD and CARP works.
        """

        self.data = data
