import re
import subprocess

from collections import namedtuple

RE_SAMR_ENUMDOMAINS = re.compile(r"name:\[(?P<name>\w+)\] idx:\[(?P<idx>\w+)\]")
RE_SAMR_ENUMDOMUSER = re.compile(r"user:\[(?P<user>\w+)\] rid:\[(?P<rid>\w+)\]")

class MS_RPC():
    """
    Thin wrapper around rpcclient. As needed we can use python bindings.
    and use this to hold state.
    """
    def __init__(self, **kwargs):
        self.user = kwargs.get('username')
        self.passwd = kwargs.get('password')
        self.workgroup = kwargs.get('workgroup')
        self.kerberos = kwargs.get('use_kerberos', False)
        self.realm = kwargs.get('realm')
        self.host = kwargs.get('host')
        self.smb1 = kwargs.get('smb1', False)

    def connect(self):
        # currently connect() and disconnect() are no-ops
        # This is placeholder for future python binding usage.
        return

    def disconnect(self):
        return

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, tp, value, traceback):
        self.disconnect()

    def _get_connection_subprocess_args(self):
        # NOTE: on failure rpcclient will return 1 with error written to stdout
        args = ['rpcclient']
        if self.kerberos:
            args.extend(['--use-kerberos', 'required'])
        else:
            args.extend(['-U', f'{self.user}%{self.passwd}'])

        if self.workgroup:
            args.extend(['-W', self.workgroup])

        if self.realm:
            args.extend(['--realm', self.realm])

        if self.smb1:
            args.extend(['-m', 'NT1'])

        args.append(self.host)

        return args

    # SAMR
    def _parse_samr_results(self, results, regex, to_convert):
        output = []
        for line in results.splitlines():
            if not (m:= regex.match(line.strip())):
                continue

            entry = m.groupdict()
            entry[to_convert] = int(entry[to_convert], 16)
            output.append(entry)

        return output

    def domains(self):
        cmd = self._get_connection_subprocess_args()
        cmd.extend(['-c', 'enumdomains'])
        rpc_proc = subprocess.run(cmd, capture_output=True)
        if rpc_proc.returncode != 0:
            raise RuntimeError(rpc_proc.stdout.decode())

        return self._parse_samr_results(
            rpc_proc.stdout.decode(),
            RE_SAMR_ENUMDOMAINS,
            'idx'
        )

    def users(self):
        cmd = self._get_connection_subprocess_args()
        cmd.extend(['-c', 'enumdomusers'])
        rpc_proc = subprocess.run(cmd, capture_output=True)
        if rpc_proc.returncode != 0:
            raise RuntimeError(rpc_proc.stdout.decode())

        return self._parse_samr_results(
            rpc_proc.stdout.decode(),
            RE_SAMR_ENUMDOMUSER,
            'rid'
        )

    # SRVSVC
    def shares(self):
        shares = []
        entry = None

        cmd = self._get_connection_subprocess_args()
        cmd.extend(['-c', 'netshareenumall'])
        rpc_proc = subprocess.run(cmd, capture_output=True)
        if rpc_proc.returncode != 0:
            raise RuntimeError(rpc_proc.stdout.decode())

        for idx, line in enumerate(rpc_proc.stdout.decode().splitlines()):
            k, v = line.strip().split(':', 1)

            # use modulo wrap-around to create new entries based on stdout
            if idx % 4 == 0:
                entry = {k: v.strip()}
                shares.append(entry)
            else:
                entry.update({k: v.strip()})

        return shares
