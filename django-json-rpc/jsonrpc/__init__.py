import re
from inspect import getargspec
from functools import wraps
from django.utils.datastructures import SortedDict
from jsonrpc.site import jsonrpc_site
from jsonrpc.types import *
from jsonrpc.exceptions import *

default_site = jsonrpc_site
KWARG_RE = re.compile(
  r'\s*(?P<arg_name>[a-zA-Z0-9_]+)\s*=\s*(?P<arg_type>[a-zA-Z]+)\s*$')
SIG_RE = re.compile(
  r'\s*(?P<method_name>[a-zA-Z0-9._]+)\s*(\((?P<args_sig>[^)].*)?\)'
  r'\s*(\->\s*(?P<return_sig>.*))?)?\s*$')

class JSONRPCTypeCheckingUnavailable(Exception): pass

def _type_checking_available(sig='', validate=False):
  if not hasattr(type, '__eq__') and validate: # and False:
    raise JSONRPCTypeCheckingUnavailable(
      'Type checking is not available in your version of Python '
      'which is only available in Python 2.6 or later. Use Python 2.6 '
      'or later or disable type checking in %s' % sig)

def _validate_arg(value, expected):
  "Returns whether or not ``value`` is the ``expected`` type."
  if type(value) == expected:
    return True
  return False

def _eval_arg_type(arg_type, T=Any, arg=None, sig=None):
  """
  Returns a type from a snippit of python source. Should normally be
  something just like 'str' or 'Object'.
  
    arg_type      the source to be evaluated
    T             the default type
    arg           context of where this type was extracted
    sig           context from where the arg was extracted
  
  Returns a type or a Type
  """
  try:
    T = eval(arg_type)
  except Exception, e:
    raise ValueError('The type of %s could not be evaluated in %s for %s: %s' %
                    (arg_type, arg, sig, str(e)))
  else:
    if type(T) not in (type, Type):
      raise TypeError('%s is not a valid type in %s for %s' %
                      (repr(T), arg, sig))
    return T

def _parse_sig(sig, arg_names, validate=False):
  """
  Parses signatures into a ``SortedDict`` of paramName => type.
  Numerically-indexed arguments that do not correspond to an argument
  name in python (ie: it takes a variable number of arguments) will be
  keyed as the stringified version of it's index.
  
    sig         the signature to be parsed
    arg_names   a list of argument names extracted from python source
  
  Returns a tuple of (method name, types dict, return type)
  """
  d = SIG_RE.match(sig)
  if not d:
    raise ValueError('Invalid method signature %s' % sig)
  d = d.groupdict()
  ret = [(n, Any) for n in arg_names]
  if 'args_sig' in d and type(d['args_sig']) is str and d['args_sig'].strip():
    for i, arg in enumerate(d['args_sig'].strip().split(',')):
      _type_checking_available(sig, validate)
      if '=' in arg:
        if not type(ret) is SortedDict:
          ret = SortedDict(ret)
        dk = KWARG_RE.match(arg)
        if not dk:
          raise ValueError('Could not parse arg type %s in %s' % (arg, sig))
        dk = dk.groupdict()
        if not sum([(k in dk and type(dk[k]) is str and bool(dk[k].strip()))
            for k in ('arg_name', 'arg_type')]):
          raise ValueError('Invalid kwarg value %s in %s' % (arg, sig))
        ret[dk['arg_name']] = _eval_arg_type(dk['arg_type'], None, arg, sig)
      else:
        if type(ret) is SortedDict:
          raise ValueError('Positional arguments must occur '
                           'before keyword arguments in %s' % sig)
        if len(ret) < i + 1:
          ret.append((str(i), _eval_arg_type(arg, None, arg, sig)))
        else:
          ret[i] = (ret[i][0], _eval_arg_type(arg, None, arg, sig))
  if not type(ret) is SortedDict:
    ret = SortedDict(ret)
  return (d['method_name'], 
          ret, 
          (_eval_arg_type(d['return_sig'], Any, 'return', sig)
            if d['return_sig'] else Any))

def _inject_args(sig, types):
  """
  A function to inject arguments manually into a method signature before
  it's been parsed. If using keyword arguments use 'kw=type' instead in
  the types array.
    
    sig     the string signature
    types   a list of types to be inserted
    
  Returns the altered signature.
  """
  if '(' in sig:
    parts = sig.split('(')
    sig = '%s(%s%s%s' % (
      parts[0], ', '.join(types), 
      (', ' if parts[1].index(')') > 0 else ''), parts[1]
    )
  else:
    sig = '%s(%s)' % (sig, ', '.join(types))
  return sig

def jsonrpc_method(name, authenticated=False, safe=False, validate=False,
                   site=default_site):
  """
  Wraps a function turns it into a json-rpc method. Adds several attributes
  to the function speific to the JSON-RPC machinery and adds it to the default
  jsonrpc_site if one isn't provided. You must import the module containing
  these functions in your urls.py.
  
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
    
  """
  def decorator(func):
    arg_names = getargspec(func)[0][1:]
    X = {'name': name, 'arg_names': arg_names}
    if authenticated:
      if authenticated is True:
        # TODO: this is an assumption
        X['arg_names'] = ['username', 'password'] + X['arg_names']
        X['name'] = _inject_args(X['name'], ('String', 'String'))
        from django.contrib.auth import authenticate
        from django.contrib.auth.models import User
      else:
        authenticate = authenticated
      @wraps(func)  
      def _func(request, *args, **kwargs):
        user = getattr(request, 'user', None)
        is_authenticated = getattr(user, 'is_authenticated', lambda: False)
        if ((user is not None 
              and callable(is_authenticated) and not is_authenticated()) 
            or user is None):
          user = None
          try:
            creds = args[:2]
            user = authenticate(username=creds[0], password=creds[1])
            if user is not None:
              args = args[2:]
          except IndexError: 
            if 'username' in kwargs and 'password' in kwargs:
              user = authenticate(username=kwargs['username'],
                                  password=kwargs['password'])
              if user is not None:
                kwargs.pop('username')
                kwargs.pop('password')
            else:
              raise InvalidParamsError(
                'Authenticated methods require at least '
                '[username, password] or {username: password:} arguments')
          if user is None:
            raise InvalidCredentialsError
          request.user = user
        return func(request, *args, **kwargs)
    else:
      _func = func
    method, arg_types, return_type = \
      _parse_sig(X['name'], X['arg_names'], validate)
    _func.json_args = X['arg_names']
    _func.json_arg_types = arg_types
    _func.json_return_type = return_type
    _func.json_method = method
    _func.json_safe = safe
    _func.json_sig = X['name']
    _func.json_validate = validate
    site.register(method, _func)
    return _func
  return decorator
