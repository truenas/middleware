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

    _gname = None
    gname = None
    name = None
    view = None
    args = ()
    kwargs ={}
    url = None
    icon = None
    model = None
    app_name = None
    append_to = None
    action = None
    type = None
    order_child = None
    order = None
    append_app = None
    option_list = []

    _children = []

    def __init__(self, gname=None, **kwargs):
        self._children = []

        for key, val in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)
            else:
                raise Exception("Attribute '%s' is not allowed" % key)

        if gname is not None:
            self.gname = gname
        elif self.gname is None:
            self.gname = unicode(self.name)
        #if self.name is None:
        #    raise ValueError(_("You must define a name"))

    def __setattr__(self, name, value):
        if not hasattr(self, name):
            raise Exception("Attribute '%s' not allowed" % name)
        super(TreeType, self).__setattr__(name, value)

    def get_absolute_url(self):
        if not self.url and self.view:
            self.url = reverse(self.view, args=self.args, kwargs=self.kwargs,
                           prefix='/')
        elif not self.url and self.view:
            self.url = '#'

        return self.url

    def __iter__(self):
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

    def find_place(self, places):
        if places:
            current_place = places.pop()
        else:
            current_place = None
        #print cur_node.gname, current_place
        if self.gname == current_place:
            for child in self:
                ret = child.find_place(list(places))
                if ret is not None:
                    return ret
            return self
        else:
            return None

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

    def __iter__(self):
        for root in list(self._roots['main']):
            yield root

    def __repr__(self):
        return u"<TreeRoots: %s>" % repr(self._roots['main'])

    def clear(self):
        self._roots.clear()

tree_roots = TreeRoots()

def _unserialize_node(entry):
    children = entry.pop('children', [])
    node = TreeNode()
    for key, val in entry.items():
        setattr(node, key, val)

    for c in children:
        child_node = _unserialize_node(c)
        node.append_child(child_node)
    return node

def unserialize_tree(data):

    nodes = []
    for entry in data:
        node = _unserialize_node(entry)
        nodes.append(node)
    return nodes
