try:
  from django.utils.translation import gettext as _
  _("You're lazy...") # this function lazy-loads settings
except (ImportError, NameError):
  _ = lambda t, *a, **k: t

class Error(Exception):
  """ Error class based on the JSON-RPC 2.0 specs 
      http://groups.google.com/group/json-rpc/web/json-rpc-1-2-proposal 
      
      code    - number
      message - string
      data    - object
      
      status  - number    from http://groups.google.com/group/json-rpc/web/json-rpc-over-http JSON-RPC over HTTP Errors section
  """
  
  code = 0
  message = None
  data = None
  status = 500
  
  def __init__(self, message=None):
    """ Setup the Exception and overwrite the default message """
    if message is not None:
      self.message = message
  
  @property
  def json_rpc_format(self):
    """ return the Exception data in a format for JSON-RPC """
    
    error = {
        'name': str(self.__class__.__name__),
        'code': self.code,
        'message': "%s: %s" % (str(self.__class__.__name__), str(self.message)),
        'data': self.data}

    from django.conf import settings
    
    if settings.DEBUG:
        import sys, traceback
        error['stack'] = traceback.format_exc()
        error['executable'] = sys.executable

    return error

# Exceptions
# from http://groups.google.com/group/json-rpc/web/json-rpc-1-2-proposal

# The error-codes -32768 .. -32000 (inclusive) are reserved for pre-defined errors. 
# Any error-code within this range not defined explicitly below is reserved for future use

class ParseError(Error):
  """ Invalid JSON. An error occurred on the server while parsing the JSON text. """
  code = -32700
  message = _('Parse error.')
  
class InvalidRequestError(Error):
  """ The received JSON is not a valid JSON-RPC Request. """
  code = -32600
  message = _('Invalid Request.')
  status = 400
  
class MethodNotFoundError(Error):
  """ The requested remote-procedure does not exist / is not available. """
  code = -32601
  message = _('Method not found.')
  status = 404
  
class InvalidParamsError(Error):
  """ Invalid method parameters. """
  code = -32602
  message = _('Invalid params.')
  
class ServerError(Error):
  """ Internal JSON-RPC error. """
  code = -32603	
  message = _('Internal error.')
  
# -32099..-32000    Server error.     Reserved for implementation-defined server-errors.  


# The remainder of the space is available for application defined errors.

class RequestPostError(InvalidRequestError):
  """ JSON-RPC requests must be POST """
  message = _('JSON-RPC requests must be POST')

class InvalidCredentialsError(Error):
  """ Invalid login credentials """
  code = 401
  message = _('Invalid login credentials')
  status = 401
  
class OtherError(Error):
  """ catchall error """
  code = 500
  message = _('Error missed by other execeptions')
  status = 500
