#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import enum
import json
import os
import re
import ssl
import urllib.request
import urllib.error
from base64 import b64encode
from subprocess import PIPE, Popen, TimeoutExpired, run
from time import sleep
from urllib.parse import urlparse

from auto_config import password, user
from middlewared.test.integration.utils import host


global header
header = {'Content-Type': 'application/json', 'Vary': 'accept'}
global authentication
authentication = (user, password)
RE_HTTPS = re.compile(r'^http(:.*)')


class HTTPResponse:
    """A wrapper to make urllib response behave like requests.Response"""
    def __init__(self, response, content):
        self.status_code = response.code
        self.headers = dict(response.headers)
        self.text = content
        self._content = content.encode('utf-8') if isinstance(content, str) else content
        self.url = response.url
        self.reason = response.reason

    def json(self):
        return json.loads(self.text)

    @property
    def content(self):
        return self._content

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise Exception(f"HTTP {self.status_code}: {self.reason}")


def http_request(method, url, data=None, headers=None, auth=None, files=None, timeout=None, verify=True):
    """A urllib-based replacement for requests.request()"""
    headers = headers or {}

    # Handle basic authentication
    if auth:
        credentials = f"{auth[0]}:{auth[1]}"
        encoded = b64encode(credentials.encode()).decode('ascii')
        headers['Authorization'] = f'Basic {encoded}'

    # Handle JSON data
    if data is not None and not files:
        if isinstance(data, (dict, list)):
            data = json.dumps(data).encode('utf-8')
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'
        elif isinstance(data, str):
            data = data.encode('utf-8')

    # Handle multipart files
    if files:
        boundary = '----WebKitFormBoundary' + ''.join([str(i) for i in range(16)])
        headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
        body_parts = []

        # Add form data if present
        if data and isinstance(data, dict):
            for key, value in data.items():
                body_parts.append(f'--{boundary}')
                body_parts.append(f'Content-Disposition: form-data; name="{key}"')
                body_parts.append('')
                body_parts.append(str(value))

        # Add files
        for field_name, file_info in files.items():
            if isinstance(file_info, tuple):
                filename, file_content = file_info[0], file_info[1]
            else:
                filename = field_name
                file_content = file_info

            # Handle io.BytesIO/io.StringIO objects
            if hasattr(file_content, 'read'):
                file_content = file_content.read()
                if hasattr(file_info, 'seek'):
                    file_info.seek(0)  # Reset position if possible

            body_parts.append(f'--{boundary}')
            body_parts.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"')
            body_parts.append('Content-Type: application/octet-stream')
            body_parts.append('')
            if isinstance(file_content, bytes):
                body_parts.append(file_content.decode('utf-8', errors='replace'))
            else:
                body_parts.append(str(file_content))

        body_parts.append(f'--{boundary}--')
        data = '\r\n'.join(str(part) for part in body_parts).encode('utf-8')

    # Create request
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    # Handle SSL verification
    if not verify:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    else:
        ssl_context = None

    try:
        # Make the request
        if timeout:
            response = urllib.request.urlopen(req, timeout=timeout, context=ssl_context)
        else:
            response = urllib.request.urlopen(req, context=ssl_context)

        content = response.read().decode('utf-8', errors='replace')
        return HTTPResponse(response, content)

    except urllib.error.HTTPError as e:
        content = e.read().decode('utf-8', errors='replace')
        # Create a response object for error cases
        error_response = type('Response', (), {
            'code': e.code,
            'headers': dict(e.headers),
            'url': e.url,
            'reason': e.reason
        })()
        return HTTPResponse(error_response, content)
    except urllib.error.URLError as e:
        # Connection errors
        raise ConnectionError(f"Failed to connect: {e.reason}")


# Convenience functions to match requests API
def http_get(url, **kwargs):
    return http_request('GET', url, **kwargs)

def http_post(url, data=None, json=None, **kwargs):
    if json is not None:
        data = json
    return http_request('POST', url, data=data, **kwargs)

def http_put(url, data=None, json=None, **kwargs):
    if json is not None:
        data = json
    return http_request('PUT', url, data=data, **kwargs)

def http_delete(url, **kwargs):
    return http_request('DELETE', url, **kwargs)


class SRVTarget(enum.Enum):
    DEFAULT = enum.auto()
    NODEA = enum.auto()
    NODEB = enum.auto()


def get_host_ip(target):
    server = host()
    if target is SRVTarget.DEFAULT:
        return server.ip
    elif target is SRVTarget.NODEA:
        return server.nodea_ip
    elif target is SRVTarget.NODEB:
        return server.nodeb_ip

    raise ValueError(f'{target}: unexpected target')


def controller_url(target=SRVTarget.DEFAULT):
    return f'http://{get_host_ip(target)}/api/v2.0'


def GET(testpath, payload=None, controller_a=False, **optional):
    data = {} if payload is None else payload
    url = controller_url(SRVTarget.NODEA if controller_a else SRVTarget.DEFAULT)
    complete_uri = testpath if testpath.startswith('http') else f'{url}{testpath}'
    if optional.get('force_ssl', False):
        complete_uri = RE_HTTPS.sub(r'https\1', complete_uri)
    timeout = optional.get('timeout', None)

    if testpath.startswith('http'):
        getit = http_get(complete_uri, timeout=timeout)
    else:
        if optional.pop("anonymous", False):
            auth = None
        else:
            auth = optional.pop("auth", authentication)
        getit = http_get(complete_uri, headers=dict(header, **optional.get("headers", {})),
                        auth=auth, data=json.dumps(data) if data else None, verify=False, timeout=timeout)
    return getit


def POST(testpath, payload=None, controller_a=False, **optional):
    data = {} if payload is None else payload
    url = controller_url(SRVTarget.NODEA if controller_a else SRVTarget.DEFAULT)
    if optional.get("use_ip_only"):
        parsed = urlparse(url)
        url = f"{parsed.scheme}://{parsed.netloc}"
    if optional.pop("anonymous", False):
        auth = None
    else:
        auth = authentication
    files = optional.get("files")
    headers = dict(({} if optional.get("force_new_headers") else header), **optional.get("headers", {}))
    if payload is None:
        postit = http_post(
            f'{url}{testpath}', headers=headers, auth=auth, files=files, verify=False)
    else:
        postit = http_post(
            f'{url}{testpath}', data=data, headers=headers, auth=auth,
            files=files, verify=False
        )
    return postit


def PUT(testpath, payload=None, controller_a=False, **optional):
    data = {} if payload is None else payload
    url = controller_url(SRVTarget.NODEA if controller_a else SRVTarget.DEFAULT)
    if optional.pop("anonymous", False):
        auth = None
    else:
        auth = authentication
    putit = http_put(f'{url}{testpath}', headers=dict(header, **optional.get("headers", {})),
                    auth=auth, data=data, verify=False)
    return putit


def DELETE(testpath, payload=None, controller_a=False, **optional):
    data = {} if payload is None else payload
    url = controller_url(SRVTarget.NODEA if controller_a else SRVTarget.DEFAULT)
    if optional.pop("anonymous", False):
        auth = None
    else:
        auth = authentication
    deleteit = http_delete(f'{url}{testpath}', headers=dict(header, **optional.get("headers", {})),
                          auth=auth,
                          data=data, verify=False)
    return deleteit


def SSH_TEST(command, username, passwrd, host=None, timeout=120):
    target = host or get_host_ip(SRVTarget.DEFAULT)

    cmd = [] if passwrd is None else ["sshpass", "-p", passwrd]
    cmd += [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "VerifyHostKeyDNS=no",
        f"{username}@{target}",
        command
    ]
    # 120 second timeout, to make sure no SSH connection hang.
    process = run(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True,
                  timeout=timeout)
    stdout = process.stdout
    stderr = process.stderr
    return {'stdout': stdout, 'stderr': stderr, 'output': stdout + stderr, 'returncode': process.returncode,
            'result': process.returncode == 0}


def async_SSH_start(command, username, passwrd, host):
    cmd = [] if passwrd is None else ["sshpass", "-p", passwrd]
    cmd += [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "VerifyHostKeyDNS=no",
        "-o",
        "LogLevel=quiet",
        f"{username}@{host}",
        command
    ]
    return Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)


def async_SSH_done(proc, timeout=120):
    try:
        outs, errs = proc.communicate(timeout=timeout)
    except TimeoutExpired:
        proc.kill()
        outs, errs = proc.communicate()

    return outs, errs


def send_file(file, destination, username, passwrd, host):
    cmd = [] if passwrd is None else ["sshpass", "-p", passwrd]
    cmd += [
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "VerifyHostKeyDNS=no",
        file,
        f"{username}@{host}:{destination}"
    ]
    process = run(cmd, stdout=PIPE, universal_newlines=True)
    output = process.stdout
    if process.returncode != 0:
        return {'result': False, 'output': output}
    else:
        return {'result': True, 'output': output}


def get_file(file, destination, username, passwrd, host):
    cmd = [] if passwrd is None else ["sshpass", "-p", passwrd]
    cmd += [
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "VerifyHostKeyDNS=no",
        f"{username}@{host}:{file}",
        destination
    ]
    process = run(cmd, stdout=PIPE, universal_newlines=True)
    output = process.stdout
    if process.returncode != 0:
        return {'result': False, 'output': output}
    else:
        return {'result': True, 'output': output}


def get_folder(folder, destination, username, passwrd, host):
    cmd = [] if passwrd is None else ["sshpass", "-p", passwrd]
    cmd += [
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "VerifyHostKeyDNS=no",
        "-r",
        f"{username}@{host}:{folder}",
        destination
    ]
    process = run(cmd, stdout=PIPE, universal_newlines=True)
    output = process.stdout
    if process.returncode != 0:
        return {'result': False, 'output': output}
    else:
        return {'result': True, 'output': output}


def RC_TEST(command):
    process = run(command, shell=True)
    if process.returncode != 0:
        return False
    else:
        return True


def return_output(command):
    process = Popen(command, shell=True, stdout=PIPE, universal_newlines=True)
    output = process.stdout.readlines()
    if len(output) == 0:
        return None
    else:
        return output[0].strip()


def cmd_test(command):
    process = run(command, shell=True, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    output = process.stdout
    err = process.stderr
    if process.returncode != 0:
        return {'result': False, 'output': output, 'stderr': err}
    else:
        return {'result': True, 'output': output}


def start_ssh_agent():
    process = run(['ssh-agent', '-s'], stdout=PIPE, universal_newlines=True)
    to_recompile = r'SSH_AUTH_SOCK=(?P<socket>[^;]+).*SSH_AGENT_PID=(?P<pid>\d+)'
    OUTPUT_PATTERN = re.compile(to_recompile, re.MULTILINE | re.DOTALL)
    match = OUTPUT_PATTERN.search(process.stdout)
    if match is None:
        return False
    else:
        agentData = match.groupdict()
        os.environ['SSH_AUTH_SOCK'] = agentData['socket']
        os.environ['SSH_AGENT_PID'] = agentData['pid']
        return True


def is_agent_setup():
    return os.environ.get('SSH_AUTH_SOCK') is not None


def setup_ssh_agent():
    if is_agent_setup():
        return True
    else:
        return start_ssh_agent()


def create_key(keyPath):
    process = run('ssh-keygen -t rsa -f %s -q -N ""' % keyPath, shell=True)
    if process.returncode != 0:
        return False
    else:
        return True


def if_key_listed():
    process = run('ssh-add -L', shell=True)
    if process.returncode != 0:
        return False
    else:
        return True


def add_ssh_key(keyPath):
    process = run(['ssh-add', keyPath])
    if process.returncode != 0:
        return False
    else:
        return True


def vm_state(vm_name):
    cmd = f'vm info {vm_name} | grep state:'
    process = run(cmd, shell=True, stdout=PIPE, universal_newlines=True)
    output = process.stdout
    return output.partition(':')[2].strip()


def vm_start(vm_name):
    cmd = ['vm', 'start', vm_name]
    process = run(cmd)
    if process.returncode != 0:
        return False
    else:
        return True


def ping_host(host, count, timeout=None):
    # this function assumes we're running on linux
    cmd = ['ping', f'-c{count}']
    if timeout is not None:
        cmd.append(f'-W{timeout}')
    cmd.append(host)

    process = run(cmd, check=False, capture_output=True)
    if timeout is not None:
        # could be that the system was rebooted and the
        # caller specified a `timeout` waiting on the
        # system to actually disappear off network OR
        # they're waiting for the system to reappear on
        # network
        return b'100% packet loss' not in process.stdout
    else:
        return process.returncode == 0


def wait_on_job(job_id, max_timeout):
    global job_results
    timeout = 0
    while True:
        job_results = GET(f'/core/get_jobs/?id={job_id}')
        job_state = job_results.json()[0]['state']
        if job_state in ('RUNNING', 'WAITING'):
            sleep(5)
        elif job_state in ('SUCCESS', 'FAILED'):
            return {'state': job_state, 'results': job_results.json()[0]}
        if timeout >= max_timeout:
            return {'state': 'TIMEOUT', 'results': job_results.json()[0]}
        timeout += 5
