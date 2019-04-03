#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import requests
from auto_config import api_url, user, password
import json
import os
from subprocess import run, Popen, PIPE
import re

global header
header = {'Content-Type': 'application/json', 'Vary': 'accept'}
global authentification
authentification = (user, password)


def GET(testpath, **optional):
    if optional.pop("anonymous", False):
        auth = None
    else:
        auth = authentification
    getit = requests.get(api_url + testpath, headers=header,
                         auth=auth)
    return getit


def GET_USER(username):
    for uid in range(1, 10000):
        results = GET("/account/users/%s/" % uid)
        if results.json()["bsdusr_username"] == username:
            userid = uid
            break
    return userid


def POST(testpath, payload=None, **optional):
    if optional.pop("anonymous", False):
        auth = None
    else:
        auth = authentification
    if payload is None:
        postit = requests.post(api_url + testpath, headers=header,
                               auth=auth)
    else:
        postit = requests.post(api_url + testpath, headers=header,
                               auth=auth, data=json.dumps(payload))
    return postit


def POST_TIMEOUT(testpath, payload, timeOut):
    if payload is None:
        postit = requests.post(api_url + testpath, headers=header,
                               auth=authentification, timeout=timeOut)
    else:
        postit = requests.post(api_url + testpath, headers=header,
                               auth=authentification, data=json.dumps(payload),
                               timeout=timeOut)
    return postit


def POSTNOJSON(testpath, payload, **optional):
    postit = requests.post(api_url + testpath, headers=header,
                           auth=authentification, data=payload)
    return postit


def PUT(testpath, payload, **optional):
    if optional.pop("anonymous", False):
        auth = None
    else:
        auth = authentification
    putit = requests.put(api_url + testpath, headers=header,
                         auth=auth, data=json.dumps(payload))
    return putit


def PUT_TIMEOUT(testpath, payload, timeOut, **optional):
    putit = requests.put(api_url + testpath, headers=header,
                         auth=authentification, data=json.dumps(payload),
                         timeout=timeOut)
    return putit


def DELETE(testpath, payload=None, **optional):
    if optional.pop("anonymous", False):
        auth = None
    else:
        auth = authentification
    deleteit = requests.delete(api_url + testpath, headers=header,
                               auth=auth,
                               data=json.dumps(payload) if payload else None)
    return deleteit


def SSH_TEST(command, username, passwrd, host):
    teststdout = "/tmp/.sshCmdTestStdOut"
    if passwrd is None:
        cmd = ""
    else:
        cmd = "sshpass -p %s " % passwrd
    cmd += "ssh -o StrictHostKeyChecking=no "
    cmd += "-o UserKnownHostsFile=/dev/null "
    cmd += "-o VerifyHostKeyDNS=no "
    cmd += "%s@%s '%s' " % (username, host, command)
    cmd += "> %s" % teststdout
    process = run(cmd, shell=True)
    output = open(teststdout, 'r').read()
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


def start_ssh_agent():
    process = run(['ssh-agent', '-s'], stdout=PIPE, universal_newlines=True)
    torecompil = 'SSH_AUTH_SOCK=(?P<socket>[^;]+).*SSH_AGENT_PID=(?P<pid>\d+)'
    OUTPUT_PATTERN = re.compile(torecompil, re.MULTILINE | re.DOTALL)
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


def ping_host(host):
    process = run(['ping', '-c', '1', host])
    if process.returncode != 0:
        return False
    else:
        return True
