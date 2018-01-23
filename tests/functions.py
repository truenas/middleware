#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import requests
from auto_config import freenas_url, password, user, ip
import json
import os
from subprocess import run, Popen, PIPE
import re

try:
    from config import BSD_HOST, BSD_USERNAME, BSD_PASSWORD
    from config import OSX_HOST, OSX_USERNAME, OSX_PASSWORD
except ImportError:
    exit()

global header
header = {'Content-Type': 'application/json', 'Vary': 'accept'}
global authentification
authentification = (user, password)


def GET(testpath):
    getit = requests.get(freenas_url + testpath, headers=header,
                         auth=authentification)
    return getit.status_code


def GET_OUTPUT(testpath, inputs):
    getit = requests.get(freenas_url + testpath, headers=header,
                         auth=authentification)
    return getit.json()[inputs]


def GET_USER(username):
    for uid in range(1, 1000):
        if GET_OUTPUT("/account/users/%s/" % uid,
                      "bsdusr_username") == username:
            userid = uid
            break
    return userid


def POST(testpath, payload):
    postit = requests.post(freenas_url + testpath, headers=header,
                           auth=authentification, data=json.dumps(payload))
    return postit.status_code


def POSTNOJSON(testpath, payload):
    postit = requests.post(freenas_url + testpath, headers=header,
                           auth=authentification, data=payload)
    return postit.status_code


def PUT(testpath, payload):
    putit = requests.put(freenas_url + testpath, headers=header,
                         auth=authentification, data=json.dumps(payload))
    return putit.status_code


def DELETE(testpath):
    deleteit = requests.delete(freenas_url + testpath, headers=header,
                               auth=authentification)
    return deleteit.status_code


def DELETE_ALL(testpath, payload):
    deleteitall = requests.delete(freenas_url + testpath, headers=header,
                                  auth=authentification,
                                  data=json.dumps(payload))
    return deleteitall.status_code


def SSH_TEST(command):
    teststdout = "/tmp/.sshCmdTestStdOut"
    cmd = "sshpass -p %s " % password
    cmd += "ssh -o StrictHostKeyChecking=no "
    cmd += "-o UserKnownHostsFile=/dev/null "
    cmd += "-o VerifyHostKeyDNS=no "
    cmd += "%s@%s '%s' " % (user, ip, command)
    cmd += "> %s" % teststdout
    process = run(cmd, shell=True)
    if process.returncode != 0:
        return False
    else:
        return True


def BSD_TEST(command):
    teststdout = "/tmp/.bsdCmdTestStdOut"
    try:
        BSD_PASSWORD
        BSD_USERNAME
        BSD_HOST
    except NameError:
        return False
    else:
        cmd = "sshpass -p %s " % BSD_PASSWORD
        cmd += "ssh -o StrictHostKeyChecking=no "
        cmd += "-o UserKnownHostsFile=/dev/null "
        cmd += "-o VerifyHostKeyDNS=no "
        cmd += "%s@%s '%s' " % (BSD_USERNAME, BSD_HOST, command)
        cmd += "> %s" % teststdout
        process = run(cmd, shell=True)
        if process.returncode != 0:
            return False
        else:
            return True


def OSX_TEST(command):
    teststdout = "/tmp/.osxCmdTestStdOut"
    try:
        OSX_PASSWORD
        OSX_USERNAME
        OSX_HOST
    except NameError:
        return False
    else:
        cmd = "sshpass -p %s " % OSX_PASSWORD
        cmd += "ssh -o StrictHostKeyChecking=no "
        cmd += "-o UserKnownHostsFile=/dev/null "
        cmd += "-o VerifyHostKeyDNS=no "
        cmd += "%s@%s '%s' " % (OSX_USERNAME, OSX_HOST, command)
        cmd += "> %s" % teststdout
        process = run(cmd, shell=True)
        if process.returncode != 0:
            return False
        else:
            return True


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
