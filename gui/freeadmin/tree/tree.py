#+
# Copyright 2010 iXsystems, Inc.
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

    gname = None
    name = None
    view = None
    args = ()
    kwargs ={}
    icon = None
    model = None
    app_name = None

    @property
    def options(self):
        raise

    _children = []

    def __init__(self, gname=None, *args, **kwargs):
        self._children = []
        if gname is not None:
            self.gname = gname
        elif self.gname is None:
            self.gname = unicode(self.name)
        #if self.name is None:
        #    raise ValueError(_("You must define a name"))

    def get_absolute_url(self):
        if self.view:
            return reverse(self.view, args=self.args, kwargs=self.kwargs,
                           prefix='/')

        return '#'

    def __iter__(self):
        #print self, self._children
        for c in list(self._children):
            yield c

    def __len__(self):
        return len(self._children)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return u"<TreeType '%s'>" % self.name

    """
    Helper method to append a child to a node
     - Register the parent of the child node
     - Append child node to parent children array
    """
    def append_child(self, tnode):
        if self is tnode:
            raise Exception("Recursive tree")
        try:
            tnode = tnode()
        except:
            pass
        tnode.parent = self
        self._children.append(tnode)

    def append_children(self, children):
        for child in children:
            self.append_child(child)

    def insert_child(self, pos, tnode):
        if self is tnode:
            raise Exception("Recursive tree")
        try:
            tnode = tnode()
        except:
            pass
        tnode.parent = self
        self._children.insert(pos, tnode)

    """
    Orphan a child
    """
    def remove_child(self, tnode):
        self._children.remove(tnode)
        tnode.parent = None

    def _setIfNone(self, attr, nfrom, nto):
        if getattr(nto, attr) is None:
            setattr(nto, attr, getattr(nfrom, attr))

    def attrFrom(self, tnode):
        if not isinstance(tnode, TreeType):
            raise
        self._setIfNone("icon", tnode, self)
        self._setIfNone("model", tnode, self)
        self._setIfNone("app_name", tnode, self)
        self._setIfNone("name", tnode, self)

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

    def clear(self):
        self._roots.clear()

tree_roots = TreeRoots()
