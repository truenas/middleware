import pathlib

from middlewared.service import private, Service, ValidationErrors
from middlewared.utils.lio.config import FILEIO_DIR, IBLOCK_DIR, sanitize_lio_extent


def _tpg_params(tpg_dir: pathlib.Path) -> dict:
    """Read session parameters from tpgt_N/param/.

    LIO does not expose per-session negotiated parameters via configfs.
    The TPG-level param/ values are the configured maxima; for most sessions
    they equal the negotiated values (initiators rarely negotiate lower).
    MaxXmitDataSegmentLength has no LIO equivalent and is left absent so the
    caller keeps its default of None.
    """
    result = {}
    param_dir = tpg_dir / 'param'
    if not param_dir.exists():
        return result
    for fname, key, conv in (
        ('MaxBurstLength', 'max_burst_length', int),
        ('MaxRecvDataSegmentLength', 'max_receive_data_segment_length', int),
        ('FirstBurstLength', 'first_burst_length', int),
        ('ImmediateData', 'immediate_data', lambda v: v == 'Yes'),
    ):
        try:
            result[key] = conv((param_dir / fname).read_text().strip())
        except (OSError, ValueError):
            pass
    if 'max_receive_data_segment_length' in result:
        result['max_data_segment_length'] = result['max_receive_data_segment_length']
    return result


class iSCSILIOService(Service):
    class Config:
        namespace = 'iscsi.lio'
        private = True

    @private
    async def validate_scst_compat(self, schema_name):
        """Check that the current configuration is compatible with LIO.

        Called when switching from any SCST mode to LIO.  Returns a
        ValidationErrors object; the caller extends its own error collection
        with the result.
        """
        verrors = ValidationErrors()

        # LIO exposes exactly one global discovery-auth slot (userid /
        # password / userid_mutual / password_mutual).  SCST allows multiple
        # iscsi.auth entries to carry discovery_auth credentials, each with a
        # distinct tag.  If more than one exists the reconciler would silently
        # use only the first and drop the rest, causing any initiator that
        # relies on a non-first credential to be rejected without explanation.
        disc_auths = await self.middleware.call(
            'iscsi.auth.query', [['discovery_auth', '!=', 'NONE']]
        )
        if len(disc_auths) > 1:
            tags = ', '.join(str(a['tag']) for a in disc_auths)
            verrors.add(
                schema_name,
                f'LIO supports only one discovery authentication credential. '
                f'{len(disc_auths)} entries have discovery_auth configured '
                f'(tags: {tags}). Remove all but one before switching to LIO mode.',
            )

        # In LIO, CHAP credentials are stored per-initiator ACL entry
        # (acls/<iqn>/auth/userid + auth/password).  This requires static
        # ACLs, meaning the initiator group must list at least one specific
        # IQN.  SCST stores IncomingUser at the target level and matches any
        # initiator that presents the right credential, so wildcard initiator
        # groups work there.  Flag any CHAP/Mutual-CHAP target group whose
        # initiator group is open (no IQNs) or absent -- those targets cannot
        # authenticate initiators after the switch.
        initiator_groups = {
            ig['id']: ig['initiators']
            for ig in await self.middleware.call('iscsi.initiator.query')
        }
        targets = await self.middleware.call(
            'iscsi.target.query', [], {'select': ['name', 'groups', 'auth_networks']}
        )
        chap_open = []
        for t in targets:
            for g in t.get('groups', []):
                if g.get('authmethod') not in ('CHAP', 'CHAP_MUTUAL'):
                    continue
                ig_id = g.get('initiator')
                # No initiator group, or group is open (empty initiators list).
                if not ig_id or not initiator_groups.get(ig_id):
                    chap_open.append(t['name'])
                    break  # one error per target is enough
        if chap_open:
            names = ', '.join(chap_open)
            verrors.add(
                schema_name,
                f'LIO requires static initiator ACLs (specific IQNs) for CHAP '
                f'authentication. The following targets have CHAP configured with '
                f'an open or absent initiator group and cannot authenticate '
                f'initiators under LIO: {names}. Assign a named initiator group '
                f'with at least one IQN to each of these targets before switching.',
            )

        # In LIO each ACL entry receives credentials from whichever auth entry
        # the reconciler finds first for the referenced tag.  SCST supports
        # multiple iscsi.auth entries sharing the same tag and emits one
        # IncomingUser line per entry, so any of those credentials is accepted.
        # Under LIO, all but the first-found entry for a tag are silently
        # unusable -- initiators that authenticate with a non-first credential
        # will be rejected.  Flag any CHAP target group whose auth tag maps to
        # more than one credential entry.
        auth_tag_counts = {}
        for a in await self.middleware.call('iscsi.auth.query'):
            if a.get('user') and a.get('secret'):
                auth_tag_counts[a['tag']] = auth_tag_counts.get(a['tag'], 0) + 1

        chap_multitag = []
        for t in targets:
            for g in t.get('groups', []):
                if g.get('authmethod') not in ('CHAP', 'CHAP_MUTUAL'):
                    continue
                tag = g.get('auth')
                if tag and auth_tag_counts.get(tag, 0) > 1:
                    chap_multitag.append(f'{t["name"]} (tag {tag})')
                    break  # one error per target is enough
        if chap_multitag:
            entries = ', '.join(chap_multitag)
            verrors.add(
                schema_name,
                f'LIO supports only one CHAP credential per auth tag. The '
                f'following targets reference an auth tag with multiple '
                f'credentials: {entries}. Reduce each referenced tag to a '
                f'single credential entry before switching to LIO mode.',
            )

        # LIO has no built-in iSNS client.  If iSNS servers are configured
        # the targets will silently disappear from the iSNS namespace after
        # the switch, breaking any initiator that relies on iSNS for discovery.
        global_cfg = await self.middleware.call('iscsi.global.config')
        if global_cfg.get('isns_servers'):
            verrors.add(
                schema_name,
                'LIO does not support iSNS. iSNS servers are currently '
                'configured; initiators that use iSNS for target discovery '
                'will lose visibility of targets after switching to LIO mode. '
                'Remove all iSNS server entries before switching.',
            )

        # auth_networks provides per-target source-IP access control in SCST.
        # LIO has no equivalent configfs mechanism; enforcement would require
        # generating firewall rules, which is out of scope for the reconciler.
        # Flag targets that would lose this protection after the switch.
        net_restricted = [t['name'] for t in targets if t.get('auth_networks')]
        if net_restricted:
            names = ', '.join(net_restricted)
            verrors.add(
                schema_name,
                f'LIO does not enforce auth_networks (source-IP access '
                f'control). The following targets have auth_networks '
                f'configured and would become reachable from all IPs under '
                f'LIO: {names}. Remove the auth_networks restrictions or '
                f'implement equivalent filtering before switching.',
            )

        return verrors

    @private
    def sessions(self, global_info):
        """Enumerate active iSCSI sessions from the LIO configfs tree.

        Two session sources are consulted per TPG:

        1. Static ACL sessions (generate_node_acls=0): appear as directories under
           acls/<iqn>/ with an 'info' file that contains the connection IP.

           The kernel iscsi_target_core info file format:
               InitiatorName: iqn.xxx
               InitiatorAlias: alias
               LIO Session ID: N  SessionType: Normal
               SessionState: TARG_SESS_STATE_LOGGED_IN
               ConnectionState: TARG_CONN_STATE_LOGGED_IN CID: 0
                 Address 1.2.3.4 TCP

        2. Dynamic ACL sessions (generate_node_acls=1): the kernel only writes the
           initiator IQN to tpgt_N/dynamic_sessions, one per line.  No IP is
           available from this interface, so initiator_addr is returned as ''.

        Per-session negotiated parameters (digests, burst lengths) are not exposed
        via either configfs interface.  TPG-level param/ values are used instead;
        for most sessions they equal the negotiated values (initiators rarely
        negotiate lower).  Digest fields (not present in LIO param/) remain None.
        """
        sessions = []
        iscsi_dir = pathlib.Path('/sys/kernel/config/target/iscsi')
        if not iscsi_dir.exists():
            return sessions

        for target_dir in iscsi_dir.iterdir():
            if not target_dir.is_dir():
                continue
            target = target_dir.name
            for tpg_dir in target_dir.iterdir():
                if not tpg_dir.is_dir() or not tpg_dir.name.startswith('tpgt_'):
                    continue

                # --- Static ACL sessions (have configfs dirs with 'info' file) ---
                acls_dir = tpg_dir / 'acls'
                if acls_dir.exists():
                    for acl_dir in acls_dir.iterdir():
                        if not acl_dir.is_dir():
                            continue
                        try:
                            lines = (acl_dir / 'info').read_text().splitlines()
                        except OSError:
                            continue
                        if not lines or lines[0].startswith('No active'):
                            continue

                        initiator_alias = None
                        initiator_addr = None
                        iser = False
                        for line in lines:
                            if line.startswith('InitiatorAlias:'):
                                alias = line.split(':', 1)[1].strip()
                                initiator_alias = alias or None
                            elif 'Address' in line:
                                # "  Address 1.2.3.4 TCP"
                                parts = line.split()
                                addr_idx = parts.index('Address')
                                initiator_addr = parts[addr_idx + 1]
                                transport = (
                                    parts[addr_idx + 2]
                                    if addr_idx + 2 < len(parts)
                                    else 'TCP'
                                )
                                iser = transport == 'iSER'
                                break  # first connection is sufficient

                        if initiator_addr is None:
                            continue  # session exists but no active connection yet

                        sess = {
                            'initiator': acl_dir.name,
                            'initiator_alias': initiator_alias,
                            'target': target,
                            'target_alias': target.rsplit(':', 1)[-1],
                            'initiator_addr': initiator_addr,
                            'header_digest': None,
                            'data_digest': None,
                            'max_data_segment_length': None,
                            'max_receive_data_segment_length': None,
                            'max_xmit_data_segment_length': None,
                            'max_burst_length': None,
                            'first_burst_length': None,
                            'immediate_data': False,
                            'iser': iser,
                            'offload': False,
                        }
                        sess.update(_tpg_params(tpg_dir))
                        sessions.append(sess)

                # --- Dynamic ACL sessions (IQN-only, no IP from kernel) ---
                dyn_file = tpg_dir / 'dynamic_sessions'
                if not dyn_file.exists():
                    continue
                try:
                    content = dyn_file.read_text()
                except OSError:
                    continue
                for line in content.splitlines():
                    # Kernel page buffers may contain trailing \x00 bytes; strip() alone
                    # does not remove null bytes, so strip them explicitly first.
                    initiator = line.replace('\x00', '').strip()
                    if not initiator:
                        continue
                    sess = {
                        'initiator': initiator,
                        'initiator_alias': None,
                        'target': target,
                        'target_alias': target.rsplit(':', 1)[-1],
                        'initiator_addr': '',
                        'header_digest': None,
                        'data_digest': None,
                        'max_data_segment_length': None,
                        'max_receive_data_segment_length': None,
                        'max_xmit_data_segment_length': None,
                        'max_burst_length': None,
                        'first_burst_length': None,
                        'immediate_data': False,
                        'iser': False,
                        'offload': False,
                    }
                    sess.update(_tpg_params(tpg_dir))
                    sessions.append(sess)
        return sessions

    @private
    def resync_lun_size_for_zvol(self, name):
        (IBLOCK_DIR / sanitize_lio_extent(name) / 'control').write_text('rescan')

    @private
    def resync_lun_size_for_file(self, name):
        (FILEIO_DIR / sanitize_lio_extent(name) / 'control').write_text('rescan')
