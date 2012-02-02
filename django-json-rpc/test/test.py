import os
import sys
import unittest
try:
  import subprocess
except ImportError:
  import subprocess_ as subprocess
import time
import urllib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

TEST_DEFAULTS = {
  'ROOT_URLCONF': 'jsontesturls',
  'DEBUG': True,
  'DEBUG_PROPAGATE_EXCEPTIONS': True,
  'DATETIME_FORMAT': 'N j, Y, P',
  'USE_I18N': False,
  'INSTALLED_APPS': (
    'jsonrpc',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions'),
  'DATABASE_ENGINE': 'sqlite3',
  'DATABASE_NAME': 'test.sqlite3',
  'MIDDLEWARE_CLASSES': (
      'django.middleware.common.CommonMiddleware',
      'django.contrib.sessions.middleware.SessionMiddleware',
      'django.middleware.csrf.CsrfViewMiddleware',
      'django.contrib.auth.middleware.AuthenticationMiddleware',
  ),
  'AUTHENTICATION_BACKENDS': ('django.contrib.auth.backends.ModelBackend',),
  'TEMPLATE_LOADERS': (
      'django.template.loaders.filesystem.load_template_source',
      'django.template.loaders.app_directories.load_template_source'),
}

from django.conf import settings
settings.configure(**TEST_DEFAULTS)

from django.core import management
from django.contrib.auth.models import User
from jsonrpc import jsonrpc_method, _parse_sig, Any, SortedDict
from jsonrpc.proxy import ServiceProxy
from jsonrpc._json import loads, dumps
from jsonrpc.site import validate_params
from jsonrpc.exceptions import *
from jsonrpc.types import *


def _call(host, req):
  return loads(urllib.urlopen(host, dumps(req)).read())


def json_serve_thread():
  from wsgiref.simple_server import make_server
  from django.core.handlers.wsgi import WSGIHandler
  http = make_server('', 8999, WSGIHandler())
  http.serve_forever()

@jsonrpc_method('jsonrpc.test')
def echo(request, string):
  """Returns whatever you give it."""
  return string

@jsonrpc_method('jsonrpc.testAuth', authenticated=True)
def echoAuth(requet, string):
  return string

@jsonrpc_method('jsonrpc.notify')
def notify(request, string):
  pass

@jsonrpc_method('jsonrpc.fails')
def fails(request, string):
  raise IndexError

@jsonrpc_method('jsonrpc.strangeEcho')
def strangeEcho(request, string, omg, wtf, nowai, yeswai='Default'):
  return [string, omg, wtf, nowai, yeswai]

@jsonrpc_method('jsonrpc.safeEcho', safe=True)
def safeEcho(request, string):
  return string

@jsonrpc_method('jsonrpc.strangeSafeEcho', safe=True)
def strangeSafeEcho(request, *args, **kwargs):
  return strangeEcho(request, *args, **kwargs)

@jsonrpc_method('jsonrpc.checkedEcho(string=str, string2=str) -> str', safe=True, validate=True)
def protectedEcho(request, string, string2):
  return string + string2

@jsonrpc_method('jsonrpc.checkedArgsEcho(string=str, string2=str)', validate=True)
def protectedArgsEcho(request, string, string2):
  return string + string2

@jsonrpc_method('jsonrpc.checkedReturnEcho() -> String', validate=True)
def protectedReturnEcho(request, string, string2):
  return string + string2

@jsonrpc_method('jsonrpc.authCheckedEcho(Object, Array) -> Object', validate=True)
def authCheckedEcho(request, obj1, arr1):
  return {'obj1': obj1, 'arr1': arr1}

@jsonrpc_method('jsonrpc.varArgs(String, String, str3=String) -> Array', validate=True)
def checkedVarArgsEcho(request, *args, **kw):
  return list(args) + kw.values()


class JSONRPCFunctionalTests(unittest.TestCase):
  def test_method_parser(self):
    working_sigs = [
      ('jsonrpc', 'jsonrpc', SortedDict(), Any),
      ('jsonrpc.methodName', 'jsonrpc.methodName', SortedDict(), Any),
      ('jsonrpc.methodName() -> list', 'jsonrpc.methodName', SortedDict(), list),
      ('jsonrpc.methodName(str, str, str ) ', 'jsonrpc.methodName', SortedDict([('a', str), ('b', str), ('c', str)]), Any),
      ('jsonrpc.methodName(str, b=str, c=str)', 'jsonrpc.methodName', SortedDict([('a', str), ('b', str), ('c', str)]), Any),
      ('jsonrpc.methodName(str, b=str) -> dict', 'jsonrpc.methodName', SortedDict([('a', str), ('b', str)]), dict),
      ('jsonrpc.methodName(str, str, c=Any) -> Any', 'jsonrpc.methodName', SortedDict([('a', str), ('b', str), ('c', Any)]), Any),
      ('jsonrpc(Any ) ->  Any', 'jsonrpc', SortedDict([('a', Any)]), Any),
    ]
    error_sigs = [
      ('jsonrpc(str) -> nowai', ValueError),
      ('jsonrpc(nowai) -> Any', ValueError),
      ('jsonrpc(nowai=str, str)', ValueError),
      ('jsonrpc.methodName(nowai*str) -> Any', ValueError)
    ]
    for sig in working_sigs:
      ret = _parse_sig(sig[0], list(iter(sig[2])))
      self.assertEquals(ret[0], sig[1])
      self.assertEquals(ret[1], sig[2])
      self.assertEquals(ret[2], sig[3])
    for sig in error_sigs:
      e = None
      try:
        _parse_sig(sig[0], ['a'])
      except Exception, exc:
        e = exc
      self.assert_(type(e) is sig[1])
  
  def test_validate_args(self):
    sig = 'jsonrpc(String, String) -> String'
    M = jsonrpc_method(sig, validate=True)(lambda r, s1, s2: s1+s2)
    self.assert_(validate_params(M, {'params': ['omg', u'wtf']}) is None)
    
    E = None
    try:
      validate_params(M, {'params': [['omg'], ['wtf']]})
    except Exception, e:
      E = e
    self.assert_(type(E) is InvalidParamsError)
  
  def test_validate_args_any(self):
    sig = 'jsonrpc(s1=Any, s2=Any)'
    M = jsonrpc_method(sig, validate=True)(lambda r, s1, s2: s1+s2)
    self.assert_(validate_params(M, {'params': ['omg', 'wtf']}) is None)
    self.assert_(validate_params(M, {'params': [['omg'], ['wtf']]}) is None)
    self.assert_(validate_params(M, {'params': {'s1': 'omg', 's2': 'wtf'}}) is None)
  
  def test_types(self):
    assert type(u'') == String
    assert type('') == String
    assert not type('') == Object
    assert not type([]) == Object
    assert type([]) == Array
    assert type('') == Any
    assert Any.kind('') == String
    assert Any.decode('str') == String
    assert Any.kind({}) == Object
    assert Any.kind(None) == Nil

proc = None

class ServiceProxyTest(unittest.TestCase):      
  def setUp(self):
    global proc
    if proc is None:
      proc = subprocess.Popen([sys.executable, 
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test.py'),
        'serve'])
      time.sleep(1)
    self.host = 'http://127.0.0.1:8999/json/'
  
  def tearDown(self):
    # self.proc.terminate()
    # self.proc.wait()
    pass
  
  def test_positional_args(self):
    proxy = ServiceProxy(self.host)
    self.assert_(proxy.jsonrpc.test('Hello')[u'result'] == 'Hello')
    try:
      proxy.jsonrpc.test(string='Hello')
    except Exception, e:
      self.assert_(e.args[0] == 'Unsupport arg type for JSON-RPC 1.0 '
                                '(the default version for this client, '
                                'pass version="2.0" to use keyword arguments)')
    else:
      self.assert_(False, 'Proxy didnt warn about version mismatch')
  
  def test_keyword_args(self):        
    proxy = ServiceProxy(self.host, version='2.0')
    self.assert_(proxy.jsonrpc.test(string='Hello')[u'result'] == 'Hello')
    self.assert_(proxy.jsonrpc.test('Hello')[u'result'] == 'Hello')


class JSONRPCTest(unittest.TestCase):
  def setUp(self):
    global proc
    if proc is None:
      proc = subprocess.Popen([sys.executable, 
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test.py'),
        'serve'])
      time.sleep(1)
    self.host = 'http://127.0.0.1:8999/json/'
    self.proxy10 = ServiceProxy(self.host, version='1.0')
    self.proxy20 = ServiceProxy(self.host, version='2.0')
  
  def tearDown(self):
    # self.proc.terminate()
    # self.proc.wait()
    pass
  
  def test_10(self):
    self.assertEqual(
      self.proxy10.jsonrpc.test('this is a string')[u'result'], 
      u'this is a string')
  
  def test_11(self):
    req = {
      u'version': u'1.1',
      u'method': u'jsonrpc.test',
      u'params': [u'this is a string'],
      u'id': u'holy-mother-of-god'
    }
    resp = _call(self.host, req)
    self.assertEquals(resp[u'id'], req[u'id'])
    self.assertEquals(resp[u'result'], req[u'params'][0])
  
  def test_10_notify(self):
    pass
  
  def test_11_positional_mixed_args(self):
    req = {
      u'version': u'1.1',
      u'method': u'jsonrpc.strangeEcho',
      u'params': {u'1': u'this is a string', u'2': u'this is omg', 
                  u'wtf': u'pants', u'nowai': 'nopants'},
      u'id': u'toostrange'
    }
    resp = _call(self.host, req)
    self.assertEquals(resp[u'result'][-1], u'Default')
    self.assertEquals(resp[u'result'][1], u'this is omg')
    self.assertEquals(resp[u'result'][0], u'this is a string')
    self.assert_(u'error' not in resp)
  
  def test_11_GET(self):
    pass
  
  def test_11_GET_unsafe(self):
    pass
  
  def test_11_GET_mixed_args(self):
    params = {u'1': u'this is a string', u'2': u'this is omg', 
              u'wtf': u'pants', u'nowai': 'nopants'}
    url = "%s%s?%s" % (
      self.host, 'jsonrpc.strangeSafeEcho',
      (''.join(['%s=%s&' % (k, urllib.quote(v)) for k, v in params.iteritems()])).rstrip('&')
    )
    resp = loads(urllib.urlopen(url).read())
    self.assertEquals(resp[u'result'][-1], u'Default')
    self.assertEquals(resp[u'result'][1], u'this is omg')
    self.assertEquals(resp[u'result'][0], u'this is a string')
    self.assert_(u'error' not in resp)
  
  def test_20_checked(self):
    self.assertEqual(
      self.proxy10.jsonrpc.varArgs('o', 'm', 'g')[u'result'],
      ['o', 'm', 'g']
    )
    self.assert_(self.proxy10.jsonrpc.varArgs(1,2,3)[u'error'])
  
  def test_11_service_description(self):
    pass
  
  def test_20_keyword_args(self):
    self.assertEqual(
      self.proxy20.jsonrpc.test(string='this is a string')[u'result'],
      u'this is a string')
  
  def test_20_positional_args(self):
    self.assertEqual(
      self.proxy20.jsonrpc.test('this is a string')[u'result'],
      u'this is a string')
  
  def test_20_notify(self):
    req = {
      u'jsonrpc': u'2.0', 
      u'method': u'jsonrpc.notify', 
      u'params': [u'this is a string'], 
      u'id': None
    }
    resp = urllib.urlopen(self.host, dumps(req)).read()
    self.assertEquals(resp, '')
  
  def test_20_batch(self):
    req = [{
      u'jsonrpc': u'2.0',
      u'method': u'jsonrpc.test',
      u'params': [u'this is a string'],
      u'id': u'id-'+unicode(i)
    } for i in range(5)]
    resp = loads(urllib.urlopen(self.host, dumps(req)).read())
    self.assertEquals(len(resp), len(req))
    for i, D in enumerate(resp):
      self.assertEquals(D[u'result'], req[i][u'params'][0])
      self.assertEquals(D[u'id'], req[i][u'id'])
  
  def test_20_batch_with_errors(self):
    req = [{
      u'jsonrpc': u'2.0',
      u'method': u'jsonrpc.test' if not i % 2 else u'jsonrpc.fails',
      u'params': [u'this is a string'],
      u'id': u'id-'+unicode(i)
    } for i in range(10)]
    resp = loads(urllib.urlopen(self.host, dumps(req)).read())
    self.assertEquals(len(resp), len(req))
    for i, D in enumerate(resp):
      if not i % 2:
        self.assertEquals(D[u'result'], req[i][u'params'][0])
        self.assertEquals(D[u'id'], req[i][u'id'])
        self.assert_(u'error' not in D)
      else:
        self.assert_(u'result' not in D)
        self.assert_(u'error' in D)
        self.assertEquals(D[u'error'][u'code'], 500)
  
  def test_authenticated_ok(self):
    self.assertEquals(
      self.proxy10.jsonrpc.testAuth(
        'sammeh', 'password', u'this is a string')[u'result'],
      u'this is a string')
  
  def test_authenticated_ok_kwargs(self):
    self.assertEquals(
      self.proxy20.jsonrpc.testAuth(
        username='sammeh', password='password', string=u'this is a string')[u'result'],
      u'this is a string')
  
  def test_authenticated_fail_kwargs(self):
    try:
      self.proxy20.jsonrpc.testAuth(
        username='osammeh', password='password', string=u'this is a string')
    except IOError, e:
      self.assertEquals(e.args[1], 401)
    else:
      self.assert_(False, 'Didnt return status code 401 on unauthorized access')
  
  def test_authenticated_fail(self):
    try:
      self.proxy10.jsonrpc.testAuth(
        'osammeh', 'password', u'this is a string')
    except IOError, e:
      self.assertEquals(e.args[1], 401)
    else:
      self.assert_(False, 'Didnt return status code 401 on unauthorized access')


if __name__ == '__main__':
  if len(sys.argv) > 1 and sys.argv[1].strip() == 'serve':
    management.call_command('syncdb', interactive=False)
    try:
      User.objects.create_user(username='sammeh', email='sam@rf.com', password='password').save()
    except:
      pass
    json_serve_thread()
  else:
    unittest.main()
    if proc is not None:
      proc.terminate()
      proc.wait()

