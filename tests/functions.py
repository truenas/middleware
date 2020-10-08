#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import requests
from auto_config import api_url, user, password
import json
import os
from subprocess import run, Popen, PIPE
from time import sleep
import re

if "controller1_ip" in os.environ:
    controller1_ip = os.environ["controller1_ip"]
    controller1_api_url = f'http://{controller1_ip}/api/v2.0'
else:
    controller1_api_url = api_url

global header
header = {'Content-Type': 'application/json', 'Vary': 'accept'}
global authentication
authentication = (user, password)


def GET(testpath, controller_a=False, **optional):
    url = controller1_api_url if controller_a else api_url
    if testpath.startswith('http'):
        getit = requests.get(testpath)
    else:
        if optional.pop("anonymous", False):
            auth = None
        else:
            auth = authentication
        payload = optional.get('payload') or {}
        getit = requests.get(f'{url}{testpath}', headers=header,
                             auth=auth, data=json.dumps(payload))
    return getit


def POST(testpath, payload=None, controller_a=False, **optional):
    url = controller1_api_url if controller_a else api_url
    if optional.pop("anonymous", False):
        auth = None
    else:
        auth = authentication
    if payload is None:
        postit = requests.post(f'{url}{testpath}', headers=header,
                               auth=auth)
    else:
        postit = requests.post(f'{url}{testpath}', headers=header,
                               auth=auth, data=json.dumps(payload))
    return postit


def PUT(testpath, payload, controller_a=False, **optional):
    url = controller1_api_url if controller_a else api_url
    if optional.pop("anonymous", False):
        auth = None
    else:
        auth = authentication
    putit = requests.put(f'{url}{testpath}', headers=header,
                         auth=auth, data=json.dumps(payload))
    return putit


def DELETE(testpath, payload=None, controller_a=False, **optional):
    url = controller1_api_url if controller_a else api_url
    if optional.pop("anonymous", False):
        auth = None
    else:
        auth = authentication
    deleteit = requests.delete(f'{url}{testpath}', headers=header,
                               auth=auth,
                               data=json.dumps(payload) if payload else None)
    return deleteit


def SSH_TEST(command, username, passwrd, host):
    cmd = [] if passwrd is None else ["sshpass", "-p", passwrd]
    cmd += [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "VerifyHostKeyDNS=no",
        f"{username}@{host}",
        command
    ]
    process = run(cmd, stdout=PIPE, universal_newlines=True)
    output = process.stdout
    if process.returncode != 0:
        return {'result': False, 'output': output}
    else:
        return {'result': True, 'output': output}


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
        f"{user}@{host}:{destination}"
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
        f"{user}@{host}:{file}",
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
    process = run(command, shell=True, stdout=PIPE, universal_newlines=True)
    output = process.stdout
    if process.returncode != 0:
        return {'result': False, 'output': output}
    else:
        return {'result': True, 'output': output}


def start_ssh_agent():
    process = run(['ssh-agent', '-s'], stdout=PIPE, universal_newlines=True)
    to_recompile = 'SSH_AUTH_SOCK=(?P<socket>[^;]+).*SSH_AGENT_PID=(?P<pid>\d+)'
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


def ping_host(host, count):
    process = run(['ping', '-c', f'{count}', host])
    if process.returncode != 0:
        return False
    else:
        return True


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
