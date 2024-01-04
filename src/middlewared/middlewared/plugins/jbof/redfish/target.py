import requests
import urllib3

from middlewared.service import Service

DEFAULT_REDFISH_TIMEOUT_SECS = 10
HEADER = {'Content-Type': 'application/json', 'Vary': 'accept'}
REDFISH_ROOT_PATH = '/redfish/v1'


class JBOFRedfishService(Service):

    class Config:
        namespace = 'jbof.redfish'
        private = True

    def ping(self, mgmt_ip, timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        base_url = f'https://{mgmt_ip}/{REDFISH_ROOT_PATH}'
        r = requests.get(base_url, verify=False, timeout=timeout)
        try:
            return r.json()
        except requests.exceptions.JSONDecodeError:
            return None

    def is_redfish(self, mgmt_ip, timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        try:
            data = self.ping(mgmt_ip, timeout)
            if data:
                return "RedfishVersion" in data
        except requests.exceptions.Timeout:
            self.logger.debug('Failed to query redfish host %s', mgmt_ip)
        return False

    def _members(self, mgmt_ip, mgmt_username, mgmt_password, path, timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        """Return a list containing the names of the IO Managers."""
        result = []
        r = self.make_request(mgmt_ip, 'get', path,
                              username=mgmt_username, password=mgmt_password, timeout=timeout)
        for member in r.get('Members', []):
            if member['@odata.id'].startswith(path):
                result.append(member['@odata.id'].split('/')[-1])
        return result

    def managers(self, mgmt_ip, mgmt_username, mgmt_password, timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        """Return a list containing the names of the IO Managers."""
        return self._members(mgmt_ip, mgmt_username, mgmt_password, f'{REDFISH_ROOT_PATH}/Managers', timeout)

    def ethernet_interfaces(self, mgmt_ip, mgmt_username, mgmt_password, manager, timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        """Return a list containing the names of the EthernetInterfaces in an IO Managers."""
        return self._members(mgmt_ip, mgmt_username, mgmt_password,
                             f'{REDFISH_ROOT_PATH}/Managers/{manager}/EthernetInterfaces', timeout)

    def ethernet_interface(self, mgmt_ip, mgmt_username, mgmt_password, manager, interface,
                           timeout=DEFAULT_REDFISH_TIMEOUT_SECS):
        """Return a list containing the names of the EthernetInterfaces in an IO Managers."""
        return self.make_request(mgmt_ip, 'get',
                                 f'{REDFISH_ROOT_PATH}/Managers/{manager}/EthernetInterfaces/{interface}',
                                 username=mgmt_username,
                                 password=mgmt_password,
                                 timeout=timeout)

    def make_request(self, mgmt_ip, _type, url, **kwargs):
        """
        Function is responsible for sending the API request.

        `_type`: String representing what type of http request to make
                    (i.e. get, put, post, delete)

        `url`: String representing the api endpoint to send the https
                    request. Can provide the endpoint by itself
                    (i.e. /Chassis/IOM1/NetworkAdapters) and the correct
                    prefix will be added or you can provide the full url to the
                    endpoint (i.e. http://ip-here/redfish/v1/endpoint-here)

        `kwargs['data']`: Dict representing the "payload" to send along
                    with the http request.
        """
        if _type == 'get':
            req = requests.get
        elif _type == 'post':
            req = requests.post
        elif _type == 'put':
            req = requests.put
        elif _type == 'delete':
            req = requests.delete
        else:
            raise ValueError(f'Invalid request type: {_type}')

        if not url.startswith('https://'):
            if url.startswith(REDFISH_ROOT_PATH):
                url = f'https://{mgmt_ip}{url}'
            else:
                url = f'https://{mgmt_ip}{REDFISH_ROOT_PATH}{url}'

        auth = kwargs.get('auth', None)
        if not auth:
            auth = (kwargs.get('username', 'Admin'), kwargs.get('password', ''))

        return req(url, auth=auth, verify=False, data=kwargs.get('data', {})).json()


async def setup(middleware):
    # Silence InsecureRequestWarning: Unverified HTTPS request is being made to host
    requests.packages.urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
