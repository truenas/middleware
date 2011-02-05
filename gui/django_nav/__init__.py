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
__all__ = ['nav_groups', 'Nav', 'NavOption', 'NavGroups']

from django_nav.base import nav_groups, Nav, NavOption, NavGroups

VERSION = (0, 6, 0, 'beta', 2)

def autodiscover():
    """
    Auto-discover INSTALLED_APPS tabs.py modules and fail silently when
    not present. This forces an import on them to register any tabs they
    may want.
    """
    import imp
    from django.conf import settings

    for app in settings.INSTALLED_APPS:
        # For each app, we need to look for an tabs.py inside that app's
        # package. We can't use os.path here -- recall that modules may be
        # imported different ways (think zip files) -- so we need to get
        # the app's __path__ and look for nav.py on that path.

        # Step 1: find out the app's __path__ Import errors here will (and
        # should) bubble up, but a missing __path__ (which is legal, but weird)
        # fails silently -- apps that do weird things with __path__ might
        # need to roll their own cron registration.
        try:
            app_path = __import__(app, {}, {}, [app.split('.')[-1]]).__path__
        except AttributeError:
            continue

        # Step 2: use imp.find_module to find the app's nav.py. For some
        # reason imp.find_module raises ImportError if the app can't be found
        # but doesn't actually try to import the module. So skip this app if
        # its tabs.py doesn't exist
        try:
            imp.find_module('nav', app_path)
        except ImportError:
            continue

        # Step 3: import the app's tabs file. If this has errors we want them
        # to bubble up.
        __import__("%s.nav" % app)

def get_version():
    version = '%s.%s' % (VERSION[0], VERSION[1])
    if VERSION[2]:
        version = '%s.%s' % (version, VERSION[2])
    if VERSION[3:] == ('alpha', 0):
        version = '%s pre-alpha' % version
    elif VERSION[3] != 'final':
            version = '%s %s %s' % (version, VERSION[3], VERSION[4])

    return version
