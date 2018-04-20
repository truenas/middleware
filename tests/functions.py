#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import requests
from auto_config import freenas_url, user, password
import json
import os
from subprocess import run, Popen, PIPE
import re

global header
header = {'Content-Type': 'application/json', 'Vary': 'accept'}
global authentification
authentification = (user, password)


def GET(testpath):
    getit = requests.get(freenas_url + testpath, headers=header,
                         auth=authentification)
    return getit


def GET_USER(username):
    for uid in range(1, 10000):
        results = GET("/account/users/%s/" % uid)
        if results.json()["bsdusr_username"] == username:
            userid = uid
            break
    return userid


def POST(testpath, payload):
    if payload is None:
        postit = requests.post(freenas_url + testpath, headers=header,
                               auth=authentification)
    else:
        postit = requests.post(freenas_url + testpath, headers=header,
                               auth=authentification, data=json.dumps(payload))
    return postit


def POST_TIMEOUT(testpath, payload, timeOut):
    if payload is None:
        postit = requests.post(freenas_url + testpath, headers=header,
                               auth=authentification, timeout=timeOut)
    else:
        postit = requests.post(freenas_url + testpath, headers=header,
                               auth=authentification, data=json.dumps(payload),
                               timeout=timeOut)
    return postit


def POSTNOJSON(testpath, payload):
    postit = requests.post(freenas_url + testpath, headers=header,
                           auth=authentification, data=payload)
    return postit


def PUT(testpath, payload):
    putit = requests.put(freenas_url + testpath, headers=header,
                         auth=authentification, data=json.dumps(payload))
    return putit


def PUT_TIMEOUT(testpath, payload, timeOut):
    putit = requests.put(freenas_url + testpath, headers=header,
                         auth=authentification, data=json.dumps(payload),
                         timeout=timeOut)
    return putit


def DELETE(testpath):
    deleteit = requests.delete(freenas_url + testpath, headers=header,
                               auth=authentification)
    return deleteit


def DELETE_ALL(testpath, payload):
    deleteitall = requests.delete(freenas_url + testpath, headers=header,
                                  auth=authentification,
                                  data=json.dumps(payload))
    return deleteitall


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
