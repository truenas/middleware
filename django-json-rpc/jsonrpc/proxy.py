import urllib, uuid
from django.test.client import FakePayload

from jsonrpc._json import loads, dumps
from jsonrpc.types import *

class ServiceProxy(object):
  def __init__(self, service_url, service_name=None, version='1.0'):
    self.version = str(version)
    self.service_url = service_url
    self.service_name = service_name

  def __getattr__(self, name):
    if self.service_name != None:
      name = "%s.%s" % (self.service_name, name)
    params = dict(self.__dict__, service_name=name)
    return self.__class__(**params)
  
  def __repr__(self):
    return {"jsonrpc": self.version,
            "method": self.service_name}
    
  def send_payload(self, params):
      """Performs the actual sending action and returns the result"""
      return urllib.urlopen(self.service_url,
                    dumps({
                      "jsonrpc": self.version,
                      "method": self.service_name,
                      'params': params,
                      'id': str(uuid.uuid1())})).read()
      
  def __call__(self, *args, **kwargs):
    params = kwargs if len(kwargs) else args
    if Any.kind(params) == Object and self.version != '2.0':
      raise Exception('Unsupport arg type for JSON-RPC 1.0 '
                     '(the default version for this client, '
                     'pass version="2.0" to use keyword arguments)')
    
    r = self.send_payload(params)    
    y = loads(r)
    if u'error' in y:
      try:
        from django.conf import settings
        if settings.DEBUG:
            print '%s error %r' % (self.service_name, y)
      except:
        pass
    return y

class TestingServiceProxy(ServiceProxy):
    """Service proxy which works inside Django unittests"""
    
    def __init__(self, client, *args, **kwargs):
        super(TestingServiceProxy, self).__init__(*args, **kwargs)
        self.client = client
    
    def send_payload(self, params):
        dump = dumps({"jsonrpc" : self.version,
                       "method" : self.service_name,
                       "params" : params,
                       "id" : str(uuid.uuid1())
                       })
        dump_payload = FakePayload(dump)
        response = self.client.post(self.service_url,
                          **{"wsgi.input" : dump_payload,
                          'CONTENT_LENGTH' : len(dump)})
        return response.content
            