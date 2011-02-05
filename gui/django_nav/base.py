"""
Copyright (c) 2007-2008, Dj Gilcrease
All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
from django.core.urlresolvers import reverse

class NavType(object):
    name = u'I Forgot to Name this'
    view = None
    args = ()
    kwargs ={}
    options = []
    conditional = {'function': None, 'args': [], 'kwargs': {}}

    def active_if(self, url, path):
        return path == url

    def get_absolute_url(self):
        if self.view:
            return reverse(self.view, args=self.args, kwargs=self.kwargs,
                           prefix='/')

        return '#'

class NavOption(NavType):
    template = 'django_nav/option.html'

class Nav(NavType):
    template = 'django_nav/nav.html'
    nav_group = 'main'

class NavGroups(object):
    _groups = {}
    def __new__(cls):
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        cls.__it__ = it = object.__new__(cls)
        return it

    def register(self, nav):
        """
            Register the given Nav
        """
        try:
            nav = nav()
        except TypeError:
            pass

        if not isinstance(nav, NavType):
            raise TypeError("You can only register a Nav not a %r" % nav)

        if not self._groups.has_key(nav.nav_group):
            self._groups[nav.nav_group] = []

        if nav not in self._groups[nav.nav_group]:
            self._groups[nav.nav_group].append(nav)

    def __getitem__(self, nav_group):
        return self._groups.get(nav_group, [])

    def __setitem__(self, *args):
        raise AttributeError

nav_groups = NavGroups()
