#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import enum
import json
import os
import re
from subprocess import PIPE, Popen, TimeoutExpired, run
from time import sleep
from urllib.parse import urlparse

import requests

from auto_config import password, user
from middlewared.test.integration.utils import call, host


global header
header = {'Content-Type': 'application/json', 'Vary': 'accept'}
global authentication
authentication = (user, password)
RE_HTTPS = re.compile(r'^http(:.*)')


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
        postit = requests.post(
            f'{url}{testpath}', headers=headers, auth=auth, files=files)
    else:
        postit = requests.post(
            f'{url}{testpath}', headers=headers, auth=auth,
            data=json.dumps(data), files=files
        )
    return postit


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
        "-o",
        "LogLevel=error",
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


def async_SSH_start(command, username=user, passwrd=password, host=None):
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
        "-o",
        "LogLevel=quiet",
        f"{username}@{target}",
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


def wait_on_job(job_id: int, max_timeout: int) -> dict:
    global job_results
    timeout = 0
    while True:
        job_results = call('core.get_jobs', [['id', '=', job_id]], {'get': True})
        job_state = job_results['state']

        if job_state in ('RUNNING', 'WAITING'):
            sleep(5)
        elif job_state in ('SUCCESS', 'FAILED'):
            return {'state': job_state, 'results': job_results}

        if timeout >= max_timeout:
            return {'state': 'TIMEOUT', 'results': job_results}

        timeout += 5
