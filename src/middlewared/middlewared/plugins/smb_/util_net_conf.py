import errno
import json
import subprocess

from middlewared.service_exception import CallError, MatchNotFound
from .constants import SMBCmd

CONF_JSON_VERSION = {"major": 0, "minor": 1}
NETCONF_ACTIONS = (
    'list',
    'showshare',
    'addshare',
    'delshare',
    'getparm',
    'setparm',
    'delparm',
)


def json_check_version(version):
    if version == CONF_JSON_VERSION:
        return

    raise CallError(
        "Unexpected JSON version returned from Samba utils: "
        f"[{version}]. Expected version was: [{CONF_JSON_VERSION}]. "
        "Please file a bug report at jira.ixsystems.com with this traceback."
    )


def netconf(**kwargs):
    """
    wrapper for net(8) conf. This manages the share configuration, which is stored in
    samba's registry.tdb file.
    """
    action = kwargs.get('action')
    if action not in NETCONF_ACTIONS:
        raise CallError(f'Action [{action}] is not permitted.', errno.EPERM)

    share = kwargs.get('share')
    args = kwargs.get('args', [])
    jsoncmd = kwargs.get('jsoncmd', False)
    if jsoncmd:
        cmd = [SMBCmd.NET.value, '--json', 'conf', action]
    else:
        cmd = [SMBCmd.NET.value, 'conf', action]

    if share:
        cmd.append(share)

    if args:
        cmd.extend(args)

    netconf = subprocess.run(cmd, capture_output=True, check=False)
    if netconf.returncode != 0:
        errmsg = netconf.stderr.decode().strip()
        if 'SBC_ERR_NO_SUCH_SERVICE' in errmsg or 'does not exist' in errmsg:
            svc = share if share else json.loads(args[0])['service']
            raise MatchNotFound(svc)

        elif 'SBC_ERR_INVALID_PARAM' in errmsg:
            raise CallError(errmsg, errno.EINVAL)

        raise CallError(
            f'net conf {action} [{cmd}] failed with error: {errmsg}'
        )

    if jsoncmd:
        out = netconf.stdout.decode()
        if out:
            out = json.loads(out)
    else:
        out = netconf.stdout.decode()

    return out


def reg_listshares():
    """
    Generate list of names of SMB shares in current running configuration
    """
    out = []
    res = netconf(action='list', jsoncmd=True)
    version = res.pop('version')
    json_check_version(version)

    for s in res['sections']:
        if s['is_share']:
            out.append(s['service'])

    return out


def reg_addshare(name, parameters):
    """
    add share with specified payload to running configuration
    """
    netconf(
        action='addshare',
        jsoncmd=True,
        args=[json.dumps({"service": name, "parameters": parameters})]
    )


def reg_delshare(share):
    """
    Delete share from running configuration by name
    """
    return netconf(action='delshare', share=share)


def reg_showshare(share):
    """
    Dump share running configuration
    """
    net = netconf(action='showshare', share=share, jsoncmd=True)
    version = net.pop('version')
    json_check_version(version)

    to_list = ['vfs objects', 'hosts allow', 'hosts deny']
    parameters = net.get('parameters', {})

    for p in to_list:
        if parameters.get(p):
            parameters[p]['parsed'] = parameters[p]['raw'].split()

    return net


def reg_setparm(data):
    """
    set specified parameters for the SMB share specified in the data.
    data is dict consisting of two keys `service` (share name) and
    `parameters` (dict containing parameters) as follows:

    {
      'service': share_name,
      'parameters': {'available': {'parsed': True}}
    }

    each parameter may specify `raw` or `parsed` value. In case of raw
    value it should be a string.
    """
    return netconf(action='setparm', args=[json.dumps(data)], jsoncmd=True)


def reg_delparm(data):
    """
    delete the specified parameters from the SMB share configuration.

    JSON object for input is identical format as reg_setparm.
    """
    return netconf(action='delparm', args=[json.dumps(data)], jsoncmd=True)


def reg_getparm(share, parm):
    """
    Retrieve the value of the specified parameter for the specified share

    NOTE: this only queries the registry and will not present SMB server
    default values.
    """
    to_list = ['vfs objects', 'hosts allow', 'hosts deny']
    try:
        ret = netconf(action='getparm', share=share, args=[parm]).strip()
    except CallError as e:
        if f"Error: given parameter '{parm}' is not set." in e.errmsg:
            # Copy behavior of samba python binding
            return None

        raise e from None

    return ret.split() if parm in to_list else ret
