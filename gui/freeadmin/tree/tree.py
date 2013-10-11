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
#####################################################################
import bisect

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _

class TreeType(object):
    parent = None

    gname = None
    name = None
    view = None
    args = ()
    kwargs = {}
    url = None
    icon = None
    model = None
    app_name = None
    append_to = None
    action = None
    type = None
    order_child = True
    order = None
    skip = False
    perm = None
    permission = lambda self, u: True
    append_app = True
    append_url = None
    option_list = []
    request = None

    _children = []

    def __init__(self, gname=None, **kwargs):
        self._children = []

        for key, val in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)
            else:
                raise Exception("Attribute '%s' is not allowed" % key)

        if self.app_name is not None and self.app_name.startswith('freenasUI.'):
            self.app_name = self.app_name.split('freenasUI.')[1]

        if gname is not None:
            self.gname = str(gname)
        elif self.gname is None:
            self.gname = unicode(self.name)

    def __setattr__(self, name, value):
        if not hasattr(self, name):
            raise Exception("Attribute '%s' not allowed" % name)
        if name == 'app_name' and value.startswith('freenasUI.'):
            value = value.split('freenasUI.')[1]
        super(TreeType, self).__setattr__(name, value)

    def __lt__(self, other):
        order1 = 0 if self.order is None else self.order
        order2 = 0 if other.order is None else other.order

        if order1 == order2:
            return self.name.lower() < other.name.lower()
        return order1 < order2

    def __iter__(self):
        for c in list(self._children):
            yield c

    def __len__(self):
        return len(self._children)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return u"<TreeType '%s'>" % self.name

    def get_absolute_url(self):
        if not self.url and self.view:
            if 'app' in self.kwargs:
                if self.kwargs['app'].startswith('freenasUI.'):
                    self.kwargs['app'] = self.kwargs['app'].split('freenasUI.')[1]
            self.url = reverse(self.view, args=self.args, kwargs=self.kwargs,
                           prefix='/')
        elif not self.url and self.view:
            self.url = '#'

        return self.url

    def append_child(self, tnode):
        """
        Helper method to append a child to a node
         - Register the parent of the child node
         - Append child node to parent children array
        """
        if self is tnode:
            raise Exception("Recursive tree")
        try:
            tnode = tnode()
        except:
            pass
        tnode.parent = self
        bisect.insort(self._children, tnode)

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

    def remove_child(self, tnode):
        """
        Orphan a child
        """
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
        self._setIfNone("order", tnode, self)

    def _get_path(self):
        _parent = self.parent
        parents = [self.gname]
        while _parent:
            parents.insert(0, _parent.gname)
            _parent = _parent.parent
        return parents

    def evaluate_gname(self):
        return '.'.join(self._get_path())

    def find_gname(self, gname):
        mypath = self._get_path()
        path = gname.split('.')

        if len(mypath) == len(path) and self.gname == gname:
            return self
        elif len(mypath) > len(path):
            return False

        for idx in xrange(len(mypath)):
            if mypath[idx] != path[idx]:
                return False

        idx += 1
        found = False
        current = self
        while not found:
            for child in current:
                if child.gname == path[idx]:
                    current = child
                    if len(path) == idx + 1:
                        found = True
                    else:
                        idx += 1
                    break
            else:
                break

        if found:
            return current
        return False

    def find_place(self, places):
        if places:
            current_place = places.pop()
        else:
            current_place = None

        if self.gname == current_place:
            for child in self:
                ret = child.find_place(list(places))
                if ret is not None:
                    return ret
            return self
        else:
            return None

    def pre_dehydrate(self):
        pass

    def pre_build_options(self):
        pass


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

        if tnode.tree_root not in self._roots:
            self._roots[tnode.tree_root] = []

        if tnode not in self._roots[tnode.tree_root]:
            self._roots[tnode.tree_root].append(tnode)

    def unregister(self, tnode):
        if tnode in self._roots[tnode.tree_root]:
            self._roots[tnode.tree_root].remove(tnode)

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
