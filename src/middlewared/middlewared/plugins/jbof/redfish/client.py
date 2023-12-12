import enum
import json
import logging
import requests
import urllib3

from urllib.parse import urlencode

DEFAULT_REDFISH_TIMEOUT_SECS = 10
HEADER = {'Content-Type': 'application/json', 'Vary': 'accept'}
REDFISH_ROOT_PATH = '/redfish/v1'
ODATA_ID = '@odata.id'

logger = logging.getLogger(__name__)


class InvalidCredentialsError(Exception):
    pass


class AuthMethod(enum.Enum):
    BASIC = 'basic'
    SESSION = 'session'

    def choices():
        return [x.value for x in AuthMethod]


class RedfishClient:

    client_cache = {}

    @classmethod
    def setup(cls):
        # Silence InsecureRequestWarning: Unverified HTTPS request is being made to host
        requests.packages.urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @classmethod
    def ping(cls, mgmt_ip, timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        mgmt_ip = mgmt_ip.rstrip('/')
        url = f'https://{mgmt_ip}{REDFISH_ROOT_PATH}'
        r = requests.get(url, verify=False, timeout=timeout)
        try:
            return r.json()
        except requests.exceptions.JSONDecodeError:
            return None

    @classmethod
    def is_redfish(cls, mgmt_ip, timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        try:
            data = cls.ping(mgmt_ip, timeout)
            if data:
                return "RedfishVersion" in data
        except requests.exceptions.Timeout:
            logger.debug('Failed to query redfish host %s', mgmt_ip)
        return False

    @classmethod
    def cache_set(cls, key, value):
        cls.client_cache[key] = value

    @classmethod
    def cache_get(cls, middleware, mgmt_ip):
        try:
            return cls.client_cache[mgmt_ip]
        except KeyError:
            jbofs = middleware.call_sync('jbof.query',
                                         [['OR',
                                           [['mgmt_ip1', '=', mgmt_ip],
                                            ['mgmt_ip2', '=', mgmt_ip]]]])
            for jbof in jbofs:
                redfish = RedfishClient(f'https://{mgmt_ip}', jbof['mgmt_username'], jbof['mgmt_password'])
                RedfishClient.cache_set(mgmt_ip, redfish)
            return redfish

    def __init__(self,
                 base_url,
                 username=None,
                 password=None,
                 authtype=AuthMethod.BASIC,
                 default_prefix=REDFISH_ROOT_PATH,
                 verify=False,
                 timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.authtype = self.authtype_to_enum(authtype)
        self.prefix = default_prefix
        self.verify = verify

        self.auth = None
        self.auth_token = None
        self.session_key = None
        self.authorization_key = None
        self.session_location = None
        self.timeout = timeout
        self.cache = {}

        self.root = self.get_root_object()
        try:
            self.login_url = self.root['Links']['Sessions']['@odata.id']
        except KeyError:
            self.login_url = '/redfish/v1/SessionService/Sessions'

        if username and password:
            self.login()

    @property
    def uuid(self):
        return self.root['UUID']

    @property
    def product(self):
        return self.root['Product']

    def _members(self, data):
        result = {}
        for manager in data['Members']:
            uri = manager[ODATA_ID]
            result[uri.split('/')[-1]] = uri
        return result

    def _cached_fetch(self, cache_key, uri, use_cached=True):
        if use_cached and cache_key in self.cache:
            return self.cache[cache_key]

        r = self.get(uri)
        if r.ok:
            self.cache[cache_key] = self._members(r.json())
            return self.cache[cache_key]

    def managers(self, use_cached=True):
        return self._cached_fetch('managers', '/Managers', use_cached)

    def mgmt_ethernet_interfaces(self, iom, use_cached=True):
        uri = self.managers()[iom] + '/EthernetInterfaces'
        return self._cached_fetch(f'{iom}/mgmt_ethernet_interfaces', uri, use_cached)

    def network_device_functions(self, iom, use_cached=True):
        return self._cached_fetch(f'{iom}/network_device_functions', f'/Chassis/{iom}/NetworkAdapters/1/NetworkDeviceFunctions', use_cached)

    def fabric_ethernet_interfaces(self, use_cached=True):
        result = []
        for iom in self.managers(use_cached):
            for ndfuri in self.network_device_functions(iom, use_cached).values():
                result.append(f'{ndfuri}/EthernetInterfaces/1')
        result.sort()
        return result

    def get_uri(self, uri, use_cached=True):
        if use_cached and uri in self.cache:
            return self.cache[uri]

        r = self.get(uri)
        if r.ok:
            self.cache[uri] = r.json()
            return self.cache[uri]

    def get_root_object(self):
        try:
            return self.get(self.prefix).json()
        except Exception as excp:
            raise excp

    def authtype_to_enum(self, authtype):
        if authtype in [AuthMethod.BASIC, AuthMethod.BASIC.value]:
            return AuthMethod.BASIC
        elif authtype in [AuthMethod.SESSION, AuthMethod.SESSION.value]:
            return AuthMethod.SESSION
        raise ValueError('Invalid auth method', authtype)

    def login(self, username=None, password=None, authtype=None):
        self.username = username if username else self.username
        self.password = password if password else self.password
        if authtype:
            self.authtype = self.authtype_to_enum(authtype)

        if self.authtype == AuthMethod.BASIC:
            self.get(self.login_url, auth=(self.username, self.password))
            # No exception thrown ...
            self.auth = (self.username, self.password)
        elif self.authtype == AuthMethod.SESSION:
            data = {
                'UserName': self.username,
                'Password': self.password
            }
            resp = self.post(self.login_url, data=data)
            self.resp = resp
            if not resp.ok:
                raise InvalidCredentialsError('Could not authenticate credentials supplied')

            self.auth_token = resp.headers.get('X-Auth-Token')
            if self.auth_token:
                self.session_id = resp.json()['Id']
                self.session_location = resp.headers.get('Location')
        else:
            raise ValueError('Invalid auth supplied:', authtype)

    def logout(self):
        if self.authtype == AuthMethod.BASIC:
            self.auth = None
        elif self.authtype == AuthMethod.SESSION:
            self.delete(self.session_location)
            self.auth_token = self.session_id = self.session_location = None
        self.username = None
        self.password = None

    def get(self, url, **kwargs):
        return self._make_request('get', url, **kwargs)

    def post(self, url, **kwargs):
        return self._make_request('post', url, **kwargs)

    def put(self, url, **kwargs):
        return self._make_request('put', url, **kwargs)

    def delete(self, url, **kwargs):
        return self._make_request('delete', url, **kwargs)

    def _make_request(self, method, url, **kwargs):
        """
        Function is responsible for sending the API request.

        `method`: String representing what type of http request to make
                    (i.e. get, put, post, delete)

        `url`: String representing the api endpoint to send the https
                    request. Can provide the endpoint by itself
                    (i.e. /Chassis/IOM1/NetworkAdapters) and the correct
                    prefix will be added or you can provide the full url to the
                    endpoint (i.e. http://ip-here/redfish/v1/endpoint-here)

        `kwargs['data']`: Dict representing the "payload" to send along
                    with the http request.
        """
        if method == 'get':
            req = requests.get
        elif method == 'post':
            req = requests.post
        elif method == 'put':
            req = requests.put
        elif method == 'delete':
            req = requests.delete
        else:
            raise ValueError(f'Invalid request type: {method}')

        if not url.startswith('https://'):
            if url.startswith(self.prefix):
                url = f'{self.base_url}{url}'
            else:
                url = f'{self.base_url}{self.prefix}{url}'

        if 'auth' in kwargs:
            auth = kwargs['auth']
        else:
            auth = self.auth
        timeout = kwargs.get('timeout', self.timeout)
        payload = kwargs.get('data', {})
        headers = kwargs.get('headers', {})

        if payload:
            if isinstance(payload, dict) or isinstance(payload, list):
                if headers.get('Content-Type', None) == 'multipart/form-data':
                    # See python-redfish-library on how to handle if ever necessary
                    raise ValueError('Currently do not support this content-type')
                else:
                    headers['Content-Type'] = 'application/json'
                    payload = json.dumps(payload)
            elif isinstance(payload, bytes):
                headers['Content-Type'] = 'application/octet-stream'
                payload = payload
            else:
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                payload = urlencode(payload)

        if self.authtype == AuthMethod.BASIC:
            r = req(url, auth=auth, verify=self.verify, headers=headers, data=payload, timeout=timeout)
        else:
            if self.auth_token:
                headers.update({'X-Auth-Token': self.auth_token})
            r = req(url, verify=self.verify, headers=headers, data=payload, timeout=timeout)
        if r.status_code == 401:
            raise InvalidCredentialsError('HTTP 401 Unauthorized returned: Invalid credentials supplied')
        return r

    def configure_fabric_interface(self,
                                   uri,
                                   address,
                                   subnet_mask,
                                   dhcp_enabled=False,
                                   gateway='0.0.0.0',
                                   mtusize=5000):
        payload = {
            "DHCPv4": {"DHCPEnabled": dhcp_enabled},
            'IPv4StaticAddresses': [{'Address': address,
                                     'Gateway': gateway,
                                     'SubnetMask': subnet_mask}],
            'MTUSize': mtusize,
        }
        self.post(uri, data=payload)
