#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
  name="django-json-rpc",
  version="0.6.2",
  description="A simple JSON-RPC implementation for Django",
  long_description="""
Features:
    * Simple, pythonic API
    * Support for Django authentication
    * Supports JSON-RPC 1.0, 1.1, 1.2 and 2.0 Spec
    * Proxy to test your JSON Service
    * Run-time type checking
    * Graphical JSON-RPC browser and web console
    * Provides system.describe


**The basic API**

::

    ## myproj/myapp/views.py
    
    from jsonrpc import jsonrpc_method
    
    @jsonrpc_method('myapp.sayHello')
    def whats_the_time(request, name='Lester'):
      return "Hello %s" % name
    
    @jsonrpc_method('myapp.gimmeThat', authenticated=True)
    def something_special(request, secret_data):
      return {'sauce': ['authenticated', 'sauce']}
    
    
    ## myproj/urls.py
    
    from django.conf.urls.defaults import *
    from jsonrpc import jsonrpc_site
    import myproj.myapp.views # you must import the views that need connected
    
    urlpatterns = patterns('', 
      url(r'^json/browse/', 'jsonrpc.views.browse', name="jsonrpc_browser"), # for the graphical browser/web console only, omissible
      url(r'^json/', jsonrpc_site.dispatch, name="jsonrpc_mountpoint"),
      (r'^json/(?P<method>[a-zA-Z0-9.]+)$', jsonrpc_site.dispatch) # for HTTP GET only, also omissible
    )


**To test your service**

You can test your service using the provided graphical browser and console,
available at http://YOUR_URL/json/browse/ (if using the url patterns from above)
or with the included ServiceProxy::

    >>> from jsonrpc.proxy import ServiceProxy

    >>> s = ServiceProxy('http://localhost:8080/json/')

    >>> s.myapp.sayHello('Sam')
    {u'error': None, u'id': u'jsonrpc', u'result': u'Hello Sam'}

    >>> s.myapp.gimmeThat('username', 'password', 'test data')
    {u'error': None, u'id': u'jsonrpc', u'result': {u'sauce': [u'authenticated', u'sauce']}}

Method Browser:

.. image:: http://samuraiblog.com/wordpress/wp-content/uploads/2009/11/jsonrpcbrowserscreen.png

We add the `jsonrpc_version` variable to the request object. It be either
'1.0', '1.1' or '2.0'. Arg.

Guide
=====

Adding JSON-RPC to your application
-----------------------------------

**1. Install django-json-rpc**

::

    git clone git://github.com/samuraisam/django-json-rpc.git
    cd django-json-rpc
    python setup.py install

    # Add 'jsonrpc' to your INSTALLED_APPS in your settings.py file

**2. Write JSON-RPC methods**

::

    from jsonrpc import jsonrpc_method

    @jsonrpc_method('app.register')
    def register_user(request, username, password):
      u = User.objects.create_user(username, 'internal@app.net', password)
      u.save()
      return u.__dict__

    @jsonrpc_method('app.change_password', authenticated=True)
    def change_password(request, new_password):
      request.user.set_password(new_password)
      request.user.save()
      return u.__dict__

**3. Add the JSON-RPC mountpoint and import your views**

::

    from jsonrpc import jsonrpc_site
    import app.views

    urlpatterns = patterns('', 
      url(r'^json/$', jsonrpc_site.dispatch, name='jsonrpc_mountpoint'),
      # ... among your other URLs
    )


The jsonrpc_method decorator
----------------------------
Wraps a function turns it into a json-rpc method. Adds several attributes to 
the function speific to the JSON-RPC machinery and adds it to the default 
jsonrpc_site if one isn't provided. You must import the module containing these
functions in your urls.py.

``jsonrpc.jsonrpc_method(name, authenticated=False, safe=False, validate=False)``

Arguments::

    name
      
        The name of your method. IE: `namespace.methodName` The method name
        can include type information, like `ns.method(String, Array) -> Nil`.

    authenticated=False   

        Adds `username` and `password` arguments to the beginning of your 
        method if the user hasn't already been authenticated. These will 
        be used to authenticate the user against `django.contrib.authenticate` 
        If you use HTTP auth or other authentication middleware, `username` 
        and `password` will not be added, and this method will only check 
        against `request.user.is_authenticated`.

        You may pass a callablle to replace `django.contrib.auth.authenticate`
        as the authentication method. It must return either a User or `None`
        and take the keyword arguments `username` and `password`.

    safe=False

        Designates whether or not your method may be accessed by HTTP GET. 
        By default this is turned off.
  
    validate=False

        Validates the arguments passed to your method based on type 
        information provided in the signature. Supply type information by 
        including types in your method declaration. Like so:

        @jsonrpc_method('myapp.specialSauce(Array, String)', validate=True)
        def special_sauce(self, ingredients, instructions):
          return SpecialSauce(ingredients, instructions)

        Calls to `myapp.specialSauce` will now check each arguments type
        before calling `special_sauce`, throwing an `InvalidParamsError` 
        when it encounters a discrepancy. This can significantly reduce the
        amount of code required to write JSON-RPC services.
  
    site=default_site
      
        Defines which site the jsonrpc method will be added to. Can be any 
        object that provides a `register(name, func)` method.


Using type checking on methods (Python 2.6 or greater)
------------------------------------------------------

When writing web services you often end up manually checking the 
types of parameters passed. django-json-rpc provides a way to eliminate 
much of that code by specifying the types in your method signature. As 
specified in the JSON-RPC spec the available types are ``Object Array Number 
Boolean String Nil`` and ``Any`` meaning any type::

      @jsonrpc_method('app.addStrings(arg1=String, arg2=String) -> String', validate=True)
      def add_strings(request, arg1, arg2):
        return arg1 + arg2

However contrived this example, a lot of extra information about our
function is available. The ``system.describe`` method will automatically
be able to provide more information about the parameters and return type.
Provide ``validate=True`` to the ``jsonrpc_method`` decorator and you can be
guaranteed to receive two string objects when ``add_strings`` is called.

**Note:** Return type information is used only for reference, return value
types are not checked.

Types can be specified a number of ways, the following are all equivalent::

      # using JSON types:
      @jsonrpc_method('app.findSelection(query=Object, limit=Number)')

      # using Python types:
      @jsonrpc_method('app.findSelection(query=dict, limit=int)')

      # with mixed keyword parameters
      @jsonrpc_method('app.findSelection(dict, limit=int)')

      # with no keyword parameters
      @jsonrpc_method('app.findSelection(dict, int)')

      # with a return value
      @jsonrpc_method('app.findSelection(dict, int) -> list')

Using the browser
-----------------

To access the browser simply add another entry to your ``urls.py`` file, before
the json dispatch one. Make sure to include the name attribute of each url::

    urlpatterns = patterns('',
      ...
      url(r'^json/browse/$', 'jsonrpc.views.browse', name='jsonrpc_browser')
      url(r'^json/', jsonrpc_site.dispatch, name="jsonrpc_mountpoint"),
      ...
    )


Enabling HTTP-GET
-----------------

JSON-RPC 1.1 includes support for methods which are accessible by HTTP GET 
which it calls idempotent. Add the following to your ``urls.py`` file to set 
up the GET URL::

    urlpatterns += patterns('', 
      (r'^json/(?P<method>[a-zA-Z0-9.-_]+)$', jsonrpc_site.dispatch),
    )

Each method that you want to be accessible by HTTP GET must also be marked safe
in the method decorator::

    @jsonrpc_method('app.trimTails(String)', safe=True)
    def trim_tails(request, arg1):
      return arg1[:5]

You can then call the method by loading ``/jsonrpc/app.trimTails?arg1=omgnowai``

Using authentication on methods
-------------------------------

There is no specific support for authentication in the JSON-RPC spec beyond 
whatever authentication the transport offers. To restrict access to methods 
to registered users provide ``authenticated=True`` to the method decorator. Doing 
so will add two arguments to the beginning of your method signature, ``username`` 
and ``password`` (and always in that order). By default, the credentials are 
authenticated against the builtin ``User`` database but any method can be used::

    @jsonrpc_method('app.thupertheecrit', authenticated=True)
    def thupertheecrit(request, value):
      p = request.user.get_profile()
      p.theecrit = value
      p.save()
      return p.__dict__

Using your own authentication method::

    def mah_authenticate(username, password):
      return CustomUserClass.authenticate(username, password)

    @jsonrpc_method('app.thupertheecrit', authenticated=mah_authenticate)
    def thupertheecrit(request, value):
      request.user.theecrit = value
      request.user.save()
      return request.user.__dict__

In case authentication is handled before your method is called, like in some 
middleware, providing ``authenticated=True`` to the method decorator will only 
check that ``request.user`` is authenticated and won't add any parameters to 
the beginning of your method.

""",
  author="Samuel Sutch",
  author_email="samuraiblog@gmail.com",
  license="MIT",
  url="http://github.com/samuraisam/django-json-rpc/tree/master",
  download_url="http://github.com/samuraisam/django-json-rpc/tree/master",
  classifiers = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Web Environment',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Topic :: Software Development :: Libraries :: Python Modules'],
  packages=['jsonrpc'],
  zip_safe = False, # we include templates and tests
  install_requires=['Django>=1.0'],
  package_data={'jsonrpc': ['templates/*']})
