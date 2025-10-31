import asyncio
import enum
import errno
import json
import logging
import socket
from urllib.parse import urlencode

import aiohttp
import requests
from middlewared.service import CallError
from middlewared.utils import MIDDLEWARE_RUN_DIR
from middlewared.utils.filter_list import filter_list
from truenas_api_client import Client
from urllib3.exceptions import InsecureRequestWarning

DEFAULT_REDFISH_TIMEOUT_SECS = 10
HEADER = {'Content-Type': 'application/json', 'Vary': 'accept'}
REDFISH_ROOT_PATH = '/redfish/v1'
ODATA_ID = '@odata.id'
LOGGER = logging.getLogger(__name__)
REDFISH_SESSIONS = '/redfish/v1/SessionService/Sessions'


class InvalidCredentialsError(Exception):
    pass


class AuthMethod(enum.Enum):
    BASIC = 'basic'
    SESSION = 'session'

    def choices():
        return [x.value for x in AuthMethod]

    def authtype_to_enum(authtype):
        if authtype in (AuthMethod.BASIC, AuthMethod.BASIC.value):
            return AuthMethod.BASIC
        elif authtype in (AuthMethod.SESSION, AuthMethod.SESSION.value):
            return AuthMethod.SESSION
        raise ValueError('Invalid auth method', authtype)


class AbstractRedfishClient:

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


class RedfishClient(AbstractRedfishClient):

    client_cache = {}

    def __init__(
        self,
        base_url,
        username=None,
        password=None,
        authtype=AuthMethod.BASIC,
        default_prefix=REDFISH_ROOT_PATH,
        verify=False,
        timeout=DEFAULT_REDFISH_TIMEOUT_SECS
    ):
        self.log_requests = False
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.authtype = AuthMethod.authtype_to_enum(authtype)
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
            self.login_url = REDFISH_SESSIONS

        if username and password:
            self.login()

    @classmethod
    def setup(cls):
        # Silence InsecureRequestWarning: Unverified HTTPS request is being made to host
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    @classmethod
    def ping(cls, mgmt_ip, timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        r = requests.get(f'https://{mgmt_ip.rstrip("/")}{REDFISH_ROOT_PATH}', verify=False, timeout=timeout)
        if r.ok:
            try:
                return r.json()
            except requests.exceptions.JSONDecodeError:
                pass

    @classmethod
    def is_redfish(cls, mgmt_ip, timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        try:
            data = cls.ping(mgmt_ip, timeout)
            return data and 'RedfishVersion' in data
        except requests.exceptions.Timeout:
            LOGGER.debug('Timed out querying redfish host %r', mgmt_ip)
        return False

    @classmethod
    def cache_set(cls, key, value):
        cls.client_cache[key] = value

    @classmethod
    def cache_get(cls, mgmt_ip, jbof_query=None):
        try:
            return cls.client_cache[mgmt_ip]
        except KeyError:
            redfish, jbofs = None, list()
            filters, options = [['OR', [['mgmt_ip1', '=', mgmt_ip], ['mgmt_ip2', '=', mgmt_ip]]]], dict()
            if jbof_query is not None:
                jbofs = jbof_query
            else:
                with Client(f'ws+unix://{MIDDLEWARE_RUN_DIR}/middlewared-internal.sock', py_exceptions=True) as c:
                    jbofs = c.call('jbof.query')

            for jbof in filter_list(jbofs, filters, options):
                redfish = RedfishClient(f'https://{mgmt_ip}', jbof['mgmt_username'], jbof['mgmt_password'])
                RedfishClient.cache_set(mgmt_ip, redfish)

            return redfish

    def _cached_fetch(self, cache_key, uri, use_cached=True):
        if use_cached and cache_key in self.cache:
            return self.cache[cache_key]

        r = self.get(uri)
        if r.ok:
            self.cache[cache_key] = self._members(r.json())
            return self.cache[cache_key]

    def chassis(self, use_cached=True):
        return self._cached_fetch('chassis', '/Chassis', use_cached)

    def managers(self, use_cached=True):
        return self._cached_fetch('managers', '/Managers', use_cached)

    def mgmt_ethernet_interfaces(self, iom, use_cached=True):
        uri = f'{self.managers()[iom]}/EthernetInterfaces'
        return self._cached_fetch(f'{iom}/mgmt_ethernet_interfaces', uri, use_cached)

    def mgmt_ip(self):
        return socket.gethostbyname(self.base_url.split('/')[-1])

    def iom_eth_mgmt_ips(self, eth_uri):
        result = []
        # Do not want any cached value.  IPs can change.
        data = self.get_uri(eth_uri, False)
        for ipv4_address in data.get('IPv4Addresses', []):
            addr = ipv4_address.get('Address')
            if addr:
                result.append(addr)
        return result

    def iom_mgmt_ips(self, iom):
        result = []
        for eth_uri in self.mgmt_ethernet_interfaces(iom).values():
            # Do not want any cached value.  IPs can change.
            result.extend(self.iom_eth_mgmt_ips(eth_uri))
        return result

    def mgmt_ips(self):
        result = []
        for iom in self.managers():
            result.extend(self.iom_mgmt_ips(iom))
        return result

    def network_device_functions(self, iom, use_cached=True):
        return self._cached_fetch(
            f'{iom}/network_device_functions',
            f'/Chassis/{iom}/NetworkAdapters/1/NetworkDeviceFunctions', use_cached
        )

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
        return self.get(self.prefix).json()

    def login(self, username=None, password=None, authtype=None):
        self.username = username if username else self.username
        self.password = password if password else self.password
        if authtype:
            self.authtype = AuthMethod.authtype_to_enum(authtype)

        if self.authtype == AuthMethod.BASIC:
            self.get(self.login_url, auth=(self.username, self.password))
            # No exception thrown ...
            self.auth = (self.username, self.password)
        elif self.authtype == AuthMethod.SESSION:
            data = {'UserName': self.username, 'Password': self.password}
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

        if self.log_requests:
            LOGGER.debug('%r %r %r', method.upper(), url, payload)

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

    def configure_fabric_interface(
        self,
        uri,
        address,
        subnet_mask,
        dhcp_enabled=False,
        gateway='0.0.0.0',
        mtusize=5000,
        enabled=True
    ):
        return self.post(uri, data={
            'DHCPv4': {'DHCPEnabled': dhcp_enabled},
            'IPv4StaticAddresses': [{'Address': address, 'Gateway': gateway, 'SubnetMask': subnet_mask}],
            'MTUSize': mtusize,
            'InterfaceEnabled': enabled,
        })

    def link_status(self, uri):
        r = self.get(uri)
        if r.ok:
            return r.json().get('LinkStatus')


class AsyncRedfishClient(AbstractRedfishClient):
    """
    Asynchronous Redfish client which supports multipath.

    Various instantiation mechanisms are available, including `cache_get` where
    objects will be cached for re-use.
    """

    # Cache where objects will be stored, keyed by JBOF UUID.
    client_cache = {}

    def __init__(
        self,
        base_urls,
        username=None,
        password=None,
        authtype=AuthMethod.BASIC,
        default_prefix=REDFISH_ROOT_PATH,
        timeout=DEFAULT_REDFISH_TIMEOUT_SECS
    ):
        self.log_requests = False
        self.base_urls = [base_url.rstrip('/') for base_url in base_urls]
        self.username = username
        self.password = password
        self.authtype = AuthMethod.authtype_to_enum(authtype)
        self.prefix = default_prefix
        self.auth = None
        self.auth_token = None
        self.session_key = None
        self.authorization_key = None
        self.session_location = {}
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.cache = {}
        self.root = None
        self._sessions = {}
        # Implement a little value cache
        self._attributes = {}
        self.logged = set()

    def _add_session(self, base_url, session):
        """Add a session corresponding to the base_url"""
        self._sessions[base_url] = session

    async def _del_session(self, base_url, session):
        """This is called when a session is no longer responding"""
        if session:
            # Don't attempt to logout.  The session is kaput
            await session.close()
        if base_url in self._sessions:
            del self._sessions[base_url]

    def sessions(self):
        """Generator to yield the (base_url, session), good ones first"""
        good = set(self._sessions.keys())
        bad = set(self.base_urls) - good
        for base_url in good:
            yield base_url, self._sessions[base_url]
        for base_url in bad:
            yield base_url, None

    def get_attribute(self, name, defval=None):
        """Retrieve some data associated with the client."""
        return self._attributes.get(name, defval)

    def set_attribute(self, name, value):
        """Associate some data with the client."""
        self._attributes[name] = value

    @classmethod
    async def create(cls,
                     base_urls,
                     username=None,
                     password=None,
                     authtype=AuthMethod.BASIC,
                     default_prefix=REDFISH_ROOT_PATH,
                     timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        """Async factory to create an AsyncRedfishClient object."""
        self = cls(base_urls, username, password, authtype, default_prefix, timeout)
        self.root = await self.get_root_object()

        try:
            self.login_url = self.root['Links']['Sessions']['@odata.id']
        except KeyError:
            self.login_url = REDFISH_SESSIONS

        return self

    @classmethod
    def cache_set(cls, key, value):
        cls.client_cache[key] = value

    @classmethod
    def cache_unset(cls, key):
        del cls.client_cache[key]

    @classmethod
    async def cache_get(cls, uuid, jbof_query=None):
        """Fetch AsyncRedfishClient object from cache, creating if necessary."""
        try:
            return cls.client_cache[uuid]
        except KeyError:
            redfish, jbofs = None, list()
            filters, options = [['uuid', '=', uuid]], dict()
            if jbof_query is not None:
                jbofs = jbof_query
            else:
                with Client(f'ws+unix://{MIDDLEWARE_RUN_DIR}/middlewared-internal.sock', private_methods=True,
                            py_exceptions=True) as c:
                    jbofs = c.call('jbof.query', filters)

            for jbof in filter_list(jbofs, filters, options):
                base_urls = []
                for key in ['mgmt_ip1', 'mgmt_ip2']:
                    if mgmt_ip := jbof.get(key):
                        base_urls.append(f'https://{mgmt_ip}')
                redfish = await cls.create(base_urls, jbof['mgmt_username'], jbof['mgmt_password'])
                cls.cache_set(uuid, redfish)

            return redfish

    async def _login(self, base_url, username=None, password=None, authtype=None):
        """Login using the specified path and credentials."""
        self.username = username if username else self.username
        self.password = password if password else self.password
        if authtype:
            self.authtype = AuthMethod.authtype_to_enum(authtype)

        async with aiohttp.ClientSession(base_url, timeout=self.timeout) as session:
            if self.authtype == AuthMethod.BASIC:
                auth = aiohttp.BasicAuth(self.username, self.password)
                async with session.get(self.login_url, ssl=False, auth=auth) as response:
                    if not response.ok:
                        raise InvalidCredentialsError('Could not authenticate credentials supplied')
                newsession = aiohttp.ClientSession(base_url, timeout=self.timeout, raise_for_status=True, auth=auth)
            elif self.authtype == AuthMethod.SESSION:
                data = {'UserName': self.username, 'Password': self.password}
                async with session.post(self.login_url, ssl=False, json=data) as response:
                    if not response.ok:
                        raise InvalidCredentialsError('Could not authenticate credentials supplied')
                    auth_token = response.headers.get('X-Auth-Token')
                    if auth_token:
                        # Save the Location for logout purposes
                        self.session_location[base_url] = response.headers.get('Location')
                newsession = aiohttp.ClientSession(base_url, timeout=self.timeout, raise_for_status=True, headers={'X-Auth-Token': auth_token})
            else:
                raise ValueError('Invalid auth supplied:', authtype)
        # Save the session for reuse
        self._add_session(base_url, newsession)
        # Clear any silenced exception logging
        try:
            self.logged.remove(base_url)
        except KeyError:
            pass
        return newsession

    async def _logout(self, base_url, session):
        if self.authtype == AuthMethod.BASIC:
            self.auth = None
        elif self.authtype == AuthMethod.SESSION:
            if location := self.session_location.get(base_url):
                async with session.delete(location, ssl=False) as response:
                    if response.ok:
                        try:
                            del self.session_location[base_url]
                        except KeyError:
                            # Should not occur, but protect in case parallel calls
                            pass

    async def get_root_object(self):
        """Fetch the root object."""
        # We're not going to try to be clever about which base_urls are used for this.
        base_url_count = len(self.base_urls)
        for index, base_url in enumerate(self.base_urls, 1):
            try:
                async with aiohttp.ClientSession(base_url, timeout=self.timeout, raise_for_status=True) as session:
                    async with session.get(self.prefix, ssl=False) as response:
                        return await response.json()
            except asyncio.TimeoutError:
                if index == base_url_count:
                    raise CallError('Connection timed out', errno.ETIMEDOUT)
                else:
                    continue
            except Exception:
                continue

        raise CallError('Failed to obtain root object', errno.EBADMSG)

    async def get(self, uri):
        if not uri.startswith(self.prefix):
            uri = f'{self.prefix}{uri}'
        # Iterate over the available paths
        for base_url, session in self.sessions():
            try:
                if not session:
                    session = await self._login(base_url)
                async with session.get(uri, ssl=False) as response:
                    if response.ok:
                        return await response.json()
            except asyncio.TimeoutError:
                LOGGER.debug('Timed out GET %r: %r', base_url, uri)
                await self._del_session(base_url, session)
                continue
            except Exception:
                if base_url not in self.logged:
                    LOGGER.debug('Failed GET %r: %r', base_url, uri, exc_info=True)
                    self.logged.add(base_url)
                await self._del_session(base_url, session)
                continue
        raise CallError(f'Failed to GET {uri}:', errno.EBADMSG)

    async def post(self, uri, **kwargs):
        if not uri.startswith(self.prefix):
            uri = f'{self.prefix}{uri}'
        payload = kwargs.get('data', {})
        # Iterate over the available paths
        for base_url, session in self.sessions():
            try:
                if not session:
                    session = await self._login(base_url)
                async with session.post(uri, ssl=False, json=payload) as response:
                    if response.ok:
                        return await response.json()
            except asyncio.TimeoutError:
                LOGGER.debug('Timed out POST %r: %r', base_url, uri)
                await self._del_session(base_url, session)
                continue
            except Exception:
                if base_url not in self.logged:
                    LOGGER.debug('Failed POST %r: %r', base_url, uri, exc_info=True)
                    self.logged.add(base_url)
                await self._del_session(base_url, session)
                continue
        raise CallError(f'Failed to POST {uri}:', errno.EBADMSG)

    async def close(self):
        for base_url, session in self._sessions.items():
            await self._logout(base_url, session)
            await session.close()
        self._sessions = {}

    async def _cached_fetch(self, cache_key, uri, use_cached=True):
        if use_cached and cache_key in self.cache:
            return self.cache[cache_key]

        r = await self.get(uri)
        if r:
            self.cache[cache_key] = self._members(r)
            return self.cache[cache_key]

    async def chassis(self, use_cached=True):
        return await self._cached_fetch('chassis', '/Chassis', use_cached)

    async def managers(self, use_cached=True):
        return await self._cached_fetch('managers', '/Managers', use_cached)
