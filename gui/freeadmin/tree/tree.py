#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _

class TreeType(object):
    parent = None

    name = None
    view = None
    args = ()
    kwargs ={}
    options = []

    #def __init__(self, *args, **kwargs):
    #    pass
    #    #if self.name is None:
    #    #    raise ValueError(_("You must define a name"))

    def get_absolute_url(self):
        if self.view:
            return reverse(self.view, args=self.args, kwargs=self.kwargs,
                           prefix='/')

        return '#'

class TreeNode(TreeType):
    pass

class TreeRoot(TreeType):
    tree_root = 'main'

class TreeRoots(object):
    _roots = {}
    def __new__(cls):
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        cls.__it__ = it = object.__new__(cls)
        return it

    def register(self, tnode):
        """
            Register the given node
        """
        try:
            tnode = tnode()
        except TypeError:
            pass

        if not isinstance(tnode, TreeType):
            raise TypeError("You can only register a Nav not a %r" % tnode)

        if not self._roots.has_key(tnode.tree_root):
            self._roots[tnode.tree_root] = []

        if tnode not in self._roots[tnode.tree_root]:
            self._roots[tnode.tree_root].append(tnode)

    def __getitem__(self, tree_root):
        return self._roots.get(tree_root, [])

    def __setitem__(self, *args):
        raise AttributeError

tree_roots = TreeRoots()
