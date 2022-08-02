from subprocess import run, STDOUT

from middlewared.service import Service, accepts, job, CallError


FW_RULES_FILE = '/tmp/fw-rules.nft'
JOB_LOCK = 'firewall_rules_update'


class NftablesService(Service):

    class Config:
        namespace = 'failover.firewall'
        private = True

    def generate_rules(self, data):
        """Generate a list of v4 and v6 firewall rules and apply them to nftables"""
        if data['drop']:
            sshport = (await self.middleware.call('ssh.config'))['tcpport']
            web = await self.middleware.call('system.general.config')

        for i in ('ip', 'ip6'):
            rules = [
                f'add table {i} filter',
                f'add chain {i} filter INPUT {{ type filter hook input priority 0; policy accept; }}',
                f'add chain {i} filter FORWARD {{ type filter hook forward priority 0; policy accept; }}',
                f'add chain {i} filter OUTPUT {{ type filter hook output priority 0; policy accept; }}',
            ]
            if data['drop']:
                # we always allow ssh and webUI access when limiting inbound connections
                rules.append(f'add rule {i} filter INPUT tcp dport {sshport} counter accept')
                rules.append(f'add rule {i} filter INPUT tcp dport {web["ui_port"]} counter accept')
                rules.append(f'add rule {i} filter INPUT tcp dport {web["ui_httpsport"]} counter accept')
                for j in data['vips']:
                    # only block the VIPs because there is the possibility of
                    # running MPIO for iSCSI which uses the non-VIP addresses of
                    # each controller on an HA system. We, obviously, dont want
                    # to block traffic there.
                    if j['type'] == 'INET' and i == 'ip':
                        rules.append(f'add rules {i} filter INPUT {i} saddr {i["address"]}/32 counter drop')
                    elif j['type'] == 'INET6' and i == 'ip6':
                        rules.append(f'add rules {i} filter INPUT {i} saddr {i["address"]}/128 counter drop')

            if i == 'ip':
                v4 = rules
            else:
                v6 = rules

        # now we write the rulesets to a file
        try:
            with open(FW_RULES_FILE, 'w+') as f:
                f.write('\n'.join(v4 + v6))  # combine the rules into a single ruleset
        except Exception as e:
            raise CallError(f'Failed writing {FW_RULES_FILE!r} with error {e}')

        # finally, we load the rulesets into nftables
        # note: this is an atomic operation (-f) so we don't need to worry about obscure race conditions
        rv = run(['nft', '-f', f'{FW_RULES_FILE}'], stdout=STDOUT, stderr=STDOUT)
        if rv.returncode:
            raise CallError(f'Failed restoring firewall rules: {rv.stdout}')

    @accepts()
    @job(lock=JOB_LOCK)
    def drop_all(self, job):
        """
        Drops (silently) all v4/v6 inbound traffic destined for the
        VIP addresses on a TrueNAS SCALE HA system. SSH and webUI
        mgmt traffic is always allowed.

        NOTE:
            Do not call this unless you know what
            you're doing or you can cause a service
            disruption.
        """
        if not self.middleware.call_sync('failover.licensed'):
            return False

        vips = []
        for i in self.middleware.call_sync('interface.query'):
            for j in i.get('failover_virtual_aliases', []):
                vips.append(j)
        if not vips:
            raise CallError('No VIP addresses detected on system')

        self.generate_rules({'drop': True, 'vips': vips})

        return True

    @accepts()
    @job(lock=JOB_LOCK)
    def accept_all(self, job):
        """Accepts all v4/v6 inbound traffic"""
        if not self.middleware.call_sync('failover.licensed'):
            return False

        self.generate_rules({'drop': False, 'vips': []})

        return True
