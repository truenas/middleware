import subprocess
import copy

from middlewared.service import Service, accepts, job, CallError


V4_FILE = '/tmp/v4-fw.rules'
V6_FILE = '/tmp/v6-fw.rules'
JOB_LOCK = 'firewall_rules_update'


class IptablesService(Service):

    class Config:
        namespace = 'failover.firewall'
        private = True

    async def generate_default_rules(self, data):
        """
        Generate a list of default firewall rules.
        """

        # this is always the beginning of the rules
        # the order of these are important
        rules = [
            '*filter',
            ':INPUT ACCEPT [0:0]',
            ':FORWARD ACCEPT [0:0]',
            ':OUTPUT ACCEPT [0:0]',
        ]

        if data['drop']:
            # we always allow ssh and webUI access when limiting inbound
            # connections (backwards compatibility with freeBSD HA)
            sshport = (await self.middleware.call('ssh.config'))['tcpport']
            web = await self.middleware.call('system.general.config')

            rules.append(f'-A INPUT -p tcp -m tcp --dport {sshport} -j ACCEPT')
            rules.append(f'-A INPUT -p tcp -m tcp --dport {web["ui_port"]} -j ACCEPT')
            rules.append(f'-A INPUT -p tcp -m tcp --dport {web["ui_httpsport"]} -j ACCEPT')

        return rules

    async def generate_rules(self, data):
        """
        Generate a list of iptables and ip6tables rules.
        """

        default_rules = await self.middleware.call('failover.firewall.generate_default_rules', data)

        v4rules = copy.deepcopy(default_rules)
        v6rules = copy.deepcopy(default_rules)

        # only block the VIPs because there is the possibility of
        # running MPIO for iSCSI which uses the non-VIP addresses of
        # each controller on an HA system. We, obviously, dont want
        # to block traffic there.
        for i in data['vips']:
            if i['type'] == 'INET':
                v4rules.append(f'-A INPUT -s {i["address"]}/32 -j DROP')
            elif i['type'] == 'INET6':
                v6rules.append(f'-A INPUT -s {i["address"]}/128 -j DROP')

        v4rules.append('COMMIT')
        v6rules.append('COMMIT')

        return v4rules, v6rules

    def write_files(self, v4rules, v6rules):
        """
        Write the firewall rules to the appropriate file(s).
        """

        try:
            with open(V4_FILE, 'w+') as f:
                # there must be a trailing newline in the file
                f.write('\n'.join(v4rules) + '\n')
        except Exception as e:
            raise CallError(f'Failed writing {V4_FILE} with error {e}')

        try:
            with open(V6_FILE, 'w+') as f:
                # there must be a trailing newline in the file
                f.write('\n'.join(v6rules) + '\n')
        except Exception as e:
            raise CallError(f'Failed writing {V6_FILE} with error {e}')

    def restore_files(self):
        # load the v4 rules
        cmd = f'iptables-restore < {V4_FILE}'
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, close_fds=True)
        out, err = p1.communicate()
        if p1.returncode:
            raise CallError(f'Failed restoring firewall rules: {err.decode("utf8", "ignore")}')

        # load the v6 rules
        cmd2 = f'ip6tables-restore < {V6_FILE}'
        p2 = subprocess.Popen(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, close_fds=True)
        out, err = p2.communicate()
        if p2.returncode:
            raise CallError(f'Failed restoring firewall rules: {err.deocde("utf8", "ignore")}')

    @accepts()
    @job(lock=JOB_LOCK)
    async def drop_all(self, job):
        """
        Drops (silently) all v4/v6 inbound traffic destined for the
        VIP addresses on a TrueNAS SCALE HA system. SSH and webUI
        mgmt traffic is always allowed.

        NOTE:
            Do not call this unless you know what
            you're doing or you can cause a service
            disruption.
        """

        if not await self.middleware.call('failover.licensed'):
            return False

        # get vips
        vips = []
        for i in await self.middleware.call('interface.query'):
            for j in i.get('failover_virtual_aliases', []):
                vips.append(j)
        if not vips:
            raise CallError('No VIP addresses detected on system')

        data = {'drop': True, 'vips': vips}
        # generate rules to DROP all inbound traffic by default
        v4rules, v6rules = await self.middleware.call('failover.firewall.generate_rules', data)

        # write the rules to the appropriate file(s)
        await self.middleware.call('failover.firewall.write_files', v4rules, v6rules)

        # now restore the files from the appropriate file(s) and enable them in iptables
        await self.middleware.call('failover.firewall.restore_files')

        return True

    @accepts()
    @job(lock=JOB_LOCK)
    async def accept_all(self, job):
        """
        Accepts all v4/v6 inbound traffic.
        """

        if not await self.middleware.call('failover.licensed'):
            return False

        data = {'drop': False, 'vips': []}
        # generate rules to ACCEPT all inbound traffic by default
        v4rules, v6rules = await self.middleware.call('failover.firewall.generate_rules', data)

        # write the rules to the appropriate file(s)
        await self.middleware.call('failover.firewall.write_files', v4rules, v6rules)

        # now restore the files from the appropriate file(s) and enable them in iptables
        await self.middleware.call('failover.firewall.restore_files')

        return True
