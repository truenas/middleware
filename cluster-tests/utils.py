import subprocess
import requests
import json
import time
import websocket
import uuid

from config import CLUSTER_INFO
from exceptions import JobTimeOut

HEADER = {'Content-Type': 'application/json', 'Vary': 'accept'}
AUTH = (CLUSTER_INFO['APIUSER'], CLUSTER_INFO['APIPASS'])


def make_ws_request(ip, payload):
    if not ip:
        ip = CLUSTER_INFO['NODE_A_IP']

    # create connection
    ws = websocket.create_connection(f'ws://{ip}:80/websocket')

    # setup features
    ws.send(json.dumps({'msg': 'connect', 'version': '1', 'support': ['1'], 'features': []}))
    ws.recv()

    # login
    id = str(uuid.uuid4())
    ws.send(json.dumps({'id': id, 'msg': 'method', 'method': 'auth.login', 'params': list(AUTH)}))
    ws.recv()

    # return the request
    payload.update({'id': id})
    ws.send(json.dumps(payload))
    return json.loads(ws.recv())


def wait_on_job(_id, ip, timeout):
    """
    Function is responsible for waiting on a job to complete.

    `_id`: Integer represening the job id
    `timeout`: Integer represening the total time to wait
                in seconds before raising JobTimeOut

    Raises `JobTimeOut` if job with `_id` doesn't complete in
        `timeout` seconds.
    """
    if timeout <= 0:
        timeout = 30

    url = f'http://{ip}/api/v2.0/core/get_jobs/?id={_id}'
    while timeout > 0:
        job = make_request('get', url).json()[0]
        state = job['state']
        if state in ('RUNNING', 'WAITING'):
            time.sleep(1)
            timeout -= 1
        elif state in ('SUCCESS', 'FAILED'):
            return {'state': state, 'result': job}
    else:
        raise JobTimeOut


def make_request(_type, url, **kwargs):
    """
    Function is responsible for sending the API request.

    `_type`: String representing what type of http request to make
                (i.e. get, put, post, delete)

    `url`: String representing the api endpoint to send the http
                request. Can provide the endpoint by itself
                (i.e. /network/config) and the correct prefix will
                be added or you can provide the full url to the
                endpoint (i.e. http://ip-here/api/v2.0/endpoint-here)

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

    if not url.startswith('http://'):
        url = f'http://{CLUSTER_INFO["NODE_A_IP"]}/api/v2.0{url}'

    return req(url, **{'headers': HEADER, 'auth': AUTH, 'data': json.dumps(kwargs.get('data', {}))})


def _run_ssh_cmd(host, action, **kwargs):
    cmd = [
        'sshpass', '-p', AUTH[1],
        'ssh' if action == 'test' else 'scp',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'VerifyHostKeyDNS=no',
    ]

    uinfo = f'{AUTH[0]}@{host}'
    if action == 'test':
        cmd.append(uinfo)
        cmd.append(kwargs['cmd'])
    elif action == 'get':
        cmd.append(f'{uinfo}:{kwargs["file"]}')
        cmd.append(kwargs['dst'])
    elif action == 'send':
        cmd.append(kwargs['file'])
        cmd.append(f'{uinfo}:{kwargs["dst"]}')

    cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return {'result': not bool(cp.returncode), 'output': cp.stdout, 'stderr': cp.stderr}


def ssh_test(host, cmd):
    return _run_ssh_cmd(host, 'test', cmd=cmd)


def ssh_get(host, _file, _dst):
    return _run_ssh_cmd(host, 'get', {'file': _file, 'dst': _dst})


def ssh_send(host, _file, _dst):
    return _run_ssh_cmd(host, 'send', {'file': _file, 'dst': _dst})
