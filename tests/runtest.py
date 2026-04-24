#!/usr/bin/env python3
# Author: Eric Turgeon
# License: BSD

from middlewared.test.integration.utils import client
from middlewared.test.integration.runner.args import parse
from middlewared.test.integration.runner.config import write_config
from middlewared.test.integration.runner.context import context_from_args
from middlewared.test.integration.runner.env import set_env
from middlewared.test.integration.runner.pytest_command import get_pytest_command
from ipaddress import ip_interface
from subprocess import run, call
from sys import exit
import os
import random
import socket
import sys
import json
import shutil

initial_env_key = set(os.environ.keys())

workdir = os.getcwd()
sys.path.append(workdir)

ixautomation_dot_conf_url = "https://raw.githubusercontent.com/iXsystems/" \
    "ixautomation/master/src/etc/ixautomation.conf.dist"
config_file_msg = "Please add config.py to freenas/tests which can be empty " \
    f"or contain settings from {ixautomation_dot_conf_url}"

if not os.path.exists('config.py'):
    print(config_file_msg)
    exit(1)

ctx = context_from_args(parse(), workdir)

set_env(ctx)
write_config(ctx)
pytest_command = get_pytest_command(ctx)


from functions import get_folder
from functions import SSH_TEST


runtest_output_dir = os.environ.get('RUNTEST_OUTPUT_DIR', 'runtest_references')
runtest_test_dir = f"{runtest_output_dir}/{os.environ['RUNTEST_TEST_NAME']}"
os.makedirs(runtest_test_dir, exist_ok=True)
shutil.copy("auto_config.py", runtest_test_dir)
with open(f"{runtest_test_dir}/result", "w") as f:
    f.write(json.dumps({
        "argv": sys.argv[1:],
        "command": pytest_command,
        "returncode": ctx.returncode,
        "artifacts": ctx.artifacts,
        "ip": ctx.ip,
        "ip2": ctx.ip2,
        "environ": {k: v for k, v in os.environ.items() if k not in initial_env_key},
    }))

sys.exit(0)

proc_returncode = call(pytest_command)


def get_cmd_result(cmd: str, target_file: str, target_ip: str):
    try:
        results = SSH_TEST(cmd, 'root', 'testing', target_ip)
    except Exception as exc:
        with open(f'{target_file}.error.txt', 'w') as f:
            f.write(f'{target_ip}: command [{cmd}] failed: {exc}\n')
            f.flush()
    else:
        with open(target_file, 'w') as f:
            f.writelines(results['stdout'])
            f.flush()


if ctx.ha:
    get_folder('/var/log', f'{artifacts}/log_nodea', 'root', 'testing', ctx.ip)
    get_folder('/var/log', f'{artifacts}/log_nodeb', 'root', 'testing', ctx.ip2)
    get_cmd_result('midclt call core.get_jobs | jq .', f'{artifacts}/core.get_jobs_nodea.json', ctx.ip)
    get_cmd_result('midclt call core.get_jobs | jq .', f'{artifacts}/core.get_jobs_nodeb.json', ctx.ip2)
    get_cmd_result('dmesg', f'{artifacts}/dmesg_nodea.json', ctx.ip)
    get_cmd_result('dmesg', f'{artifacts}/dmesg_nodeb.json', ctx.ip2)
else:
    get_folder('/var/log', f'{artifacts}/log', 'root', 'testing', ctx.ip)
    get_cmd_result('midclt call core.get_jobs | jq .', f'{artifacts}/core.get_jobs.json', ctx.ip)
    get_cmd_result('dmesg', f'{artifacts}/dmesg.json', ctx.ip)

if ctx.returncode:
    exit(proc_returncode)
