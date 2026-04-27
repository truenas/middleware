import os
import re
from subprocess import PIPE, run


def start_ssh_agent() -> bool:
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


def is_agent_setup() -> bool:
    return os.environ.get('SSH_AUTH_SOCK') is not None


def setup_ssh_agent() -> bool:
    if is_agent_setup():
        return True
    else:
        return start_ssh_agent()


def create_key(keyPath: str) -> bool:
    process = run('ssh-keygen -t rsa -f %s -q -N ""' % keyPath, shell=True)
    if process.returncode != 0:
        return False
    else:
        return True


def if_key_listed() -> bool:
    process = run('ssh-add -L', shell=True)
    if process.returncode != 0:
        return False
    else:
        return True


def add_ssh_key(keyPath: str) -> bool:
    process = run(['ssh-add', keyPath])
    if process.returncode != 0:
        return False
    else:
        return True
