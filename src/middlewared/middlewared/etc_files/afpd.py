import os
import textwrap

from middlewared.client.utils import Struct
from middlewared.utils import osc
from middlewared.plugins.afp import AFPLogLevel


def get_interface(middleware, ipaddress):
    ifaces = []
    for iface in middleware.call_sync('interface.query'):
        all_ip = [a['address'] for a in iface['aliases'] if a['type'] == 'INET']
        is_ip_exist = list(set(ipaddress).intersection(all_ip))
        if is_ip_exist:
            ifaces.append(iface['name'])

    return ifaces


def render(service, middleware):
    """
    The resulting afp.conf file will only allow kerberos authentication (add uams_gss.so)
    if a kerberos keytab is uploaded to the NAS. When afp_srv_map_acls is set to "mode"
    and the LDAP or AD directory service is enabled, the NAS is configured to query the LDAP server
    for a UUID attribute to present to MacOS clients. This is required for the permission editor to
    properly display users in the MacOS permissions editor because MacOS clients use UUIDs
    rather than UIDs and GIDs. SASL is not implemented in Netatalk, and so this feature requires
    storing the plain-text LDAP password in the afp.conf file. The default AD behavior clears
    the bindpw after successful domain join, and so additional configuration (persistently storing
    the bindpw and possibly LDAP schema changes) will be required for this feature to work correctly.
    """

    map_acls_mode = False
    ds_type = None
    if osc.IS_FREEBSD:
        afp_config = '/usr/local/etc/afp.conf'
    else:
        afp_config = '/etc/netatalk/afp.conf'

    cf_contents = []

    afp = Struct(middleware.call_sync('datastore.query', 'services.afp', [], {'get': True}))

    cf_contents.append("[Global]\n")
    uam_list = ['uams_dhx.so', 'uams_dhx2.so']
    if afp.afp_srv_guest:
        uam_list.append('uams_guest.so')
        cf_contents.append('\tguest account = %s\n' % afp.afp_srv_guest_user)
    # uams_gss.so bails out with an error if kerberos isn't configured
    if middleware.call_sync('datastore.query', 'directoryservice.kerberoskeytab', [], {'count': True}) > 0:
        uam_list.append('uams_gss.so')
    cf_contents.append('\tuam list = %s\n' % (" ").join(uam_list))

    if afp.afp_srv_bindip:
        ifaces = get_interface(middleware, afp.afp_srv_bindip)
        if ifaces:
            cf_contents.append("\tafp listen = %s\n" % ' '.join(afp.afp_srv_bindip))
            cf_contents.append("\tafp interfaces = %s\n" % ' '.join(ifaces))

    cf_contents.append("\tmax connections = %s\n" % afp.afp_srv_connections_limit)
    cf_contents.append("\tmimic model = RackMac\n")
    cf_contents.append("\tafpstats = yes\n")
    if afp.afp_srv_dbpath:
        cf_contents.append("\tvol dbnest = no\n")
        cf_contents.append("\tvol dbpath = %s\n" % afp.afp_srv_dbpath)
    else:
        cf_contents.append("\tvol dbnest = yes\n")
    if afp.afp_srv_global_aux:
        cf_contents.append("\t%s\n" % afp.afp_srv_global_aux)

    if afp.afp_srv_map_acls:
        cf_contents.append("\tmap acls = %s\n" % afp.afp_srv_map_acls)

    if afp.afp_srv_chmod_request:
        cf_contents.append("\tchmod request = %s\n" % afp.afp_srv_chmod_request)

    if afp.afp_srv_map_acls == 'mode':
        if middleware.call_sync('activedirectory.get_state') != 'DISABLED':
            ds_type = 'AD'
        elif middleware.call_sync('ldap.get_state') != 'DISABLED':
            ds_type = 'LDAP'

    if ds_type is not None:
        ds_config = {
            'bind_dn': None,
            'bind_pw': None,
            'server': None,
            'userbase': None,
            'groupbase': None,
        }
        if ds_type == 'AD':
            ad = middleware.call_sync('activedirectory.config')
            ds_config.update({
                'bind_dn': ad['bindname'],
                'bind_pw': ad['bindpw'],
                'server': ad['domainname'],
            })
        elif ds_type == 'LDAP':
            ldap = middleware.call_sync('ldap.config')
            ds_config.update({
                'bind_dn': ldap['binddn'],
                'bind_pw': ldap['bindpw'],
                'server': ldap['hostname'],
                'userbase': ldap['basedn'],
                'groupbase': ldap['basedn'],
            })

        cf_contents.append("\tldap auth method = %s\n" % "simple")
        cf_contents.append("\tldap auth dn = %s\n" % ds_config['bind_dn'])
        cf_contents.append("\tldap auth pw = %s\n" % ds_config['bind_pw'])
        cf_contents.append("\tldap server = %s\n" % ds_config['server'])

        # This should be configured when using this option
        if ds_config['userbase']:
            cf_contents.append("\tldap userbase = %s\n" % ds_config['userbase'])

        cf_contents.append("\tldap userscope = %s\n" % "sub")

        # This should be configured when using this option
        if ds_config['groupbase']:
            cf_contents.append("\tldap groupbase = %s\n" % ds_config['groupbase'])

        cf_contents.append("\tldap groupscope = %s\n" % "sub")

        cf_contents.append("\tldap user filter = %s\n" % "objectclass=user")
        cf_contents.append("\tldap group filter = %s\n" % "objectclass=group")
        cf_contents.append("\tldap uuid attr = %s\n" % "objectGUID")
        if ds_type == 'AD':
            cf_contents.append("\tldap uuid encoding = %s\n" % "ms-guid")
            cf_contents.append("\tldap name attr = %s\n" % "sAMAccountName")
            cf_contents.append("\tldap group attr = %s\n" % "sAMAccountName")

    cf_contents.append("\tlog level = default:%s\n" % AFPLogLevel[afp.afp_srv_loglevel].value)
    cf_contents.append("\n")

    locked_shares = {d['id']: d for d in middleware.call_sync('sharing.afp.query', [['locked', '=', True]])}

    for share in middleware.call_sync('datastore.query', 'sharing.afp_share', [['afp_enabled', '=', True]]):
        share = Struct(share)
        if share.id in locked_shares:
            middleware.logger.debug('Skipping generation of %r afp share because it\'s locked', share.afp_name)
            middleware.call_sync('sharing.afp.generate_locked_alert', share.id)
            continue

        if share.afp_home:
            cf_contents.append("[Homes]\n")
            cf_contents.append("\tbasedir regex = %s\n" % share.afp_path)
            if share.afp_name and share.afp_name != "Homes":
                cf_contents.append("\thome name = %s\n" % share.afp_name)
        else:
            cf_contents.append("[%s]\n" % share.afp_name)
            cf_contents.append("\tpath = %s\n" % share.afp_path)
        if share.afp_allow:
            cf_contents.append("\tvalid users = %s\n" % share.afp_allow)
        if share.afp_deny:
            cf_contents.append("\tinvalid users = %s\n" % share.afp_deny)
        if share.afp_hostsallow:
            cf_contents.append("\thosts allow = %s\n" % share.afp_hostsallow)
        if share.afp_hostsdeny:
            cf_contents.append("\thosts deny = %s\n" % share.afp_hostsdeny)
        if share.afp_ro:
            cf_contents.append("\trolist = %s\n" % share.afp_ro)
        if share.afp_rw:
            cf_contents.append("\trwlist = %s\n" % share.afp_rw)
        if share.afp_timemachine:
            cf_contents.append("\ttime machine = yes\n")
        if not share.afp_nodev:
            cf_contents.append("\tcnid dev = no\n")
        if share.afp_nostat:
            cf_contents.append("\tstat vol = no\n")
        if not share.afp_upriv:
            cf_contents.append("\tunix priv = no\n")
        else:
            if share.afp_fperm and not map_acls_mode:
                cf_contents.append("\tfile perm = %s\n" % share.afp_fperm)
            if share.afp_dperm and not map_acls_mode:
                cf_contents.append("\tdirectory perm = %s\n" % share.afp_dperm)
            if share.afp_umask and not map_acls_mode:
                cf_contents.append("\tumask = %s\n" % share.afp_umask)
        cf_contents.append("\tveto files = .windows/.mac/\n")
        if map_acls_mode:
            cf_contents.append("\tacls = yes\n")
        # Do not fail if aux params are not properly entered by the user
        try:
            aux_params = ["\t{0}\n".format(p) for p in share.afp_auxparams.split("\n")]
        except:
            pass
        else:
            cf_contents += aux_params
        # Update TimeMachine special files
        timemachine_supported_path = os.path.join(share.afp_path, ".com.apple.timemachine.supported")
        timemachine_quota_plist_path = os.path.join(share.afp_path, ".com.apple.TimeMachine.quota.plist")
        timemachine_quota_plist_managed_flag = os.path.join(share.afp_path,
                                                            ".com.apple.TimeMachine.quota.plist.FreeNAS-managed")
        if share.afp_timemachine and share.afp_timemachine_quota:
            try:
                with open(timemachine_supported_path, "w"):
                    pass
            except IOError:
                pass

            try:
                with open(timemachine_quota_plist_path, "w") as f:
                    f.write(textwrap.dedent("""\
                        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
                        <plist version="1.0">
                            <dict>
                                <key>GlobalQuota</key>
                                <integer>%d</integer>
                            </dict>
                        </plist>
                    """ % (share.afp_timemachine_quota * 1024 * 1024 * 1024)))
            except IOError:
                pass

            try:
                with open(timemachine_quota_plist_managed_flag, "w") as f:
                    pass
            except IOError:
                pass

            try:
                stat = os.stat(share.afp_path)
                os.chmod(timemachine_supported_path, 0o644)
                os.chown(timemachine_supported_path, stat.st_uid, stat.st_gid)
                os.chmod(timemachine_quota_plist_path, 0o644)
                os.chown(timemachine_quota_plist_path, stat.st_uid, stat.st_gid)
                os.chmod(timemachine_quota_plist_managed_flag, 0o644)
                os.chown(timemachine_quota_plist_managed_flag, stat.st_uid, stat.st_gid)
            except IOError:
                pass
        else:
            if os.path.exists(timemachine_quota_plist_managed_flag):
                try:
                    os.unlink(timemachine_supported_path)
                except IOError:
                    pass

                try:
                    os.unlink(timemachine_quota_plist_path)
                except IOError:
                    pass

    with open(afp_config, "w") as fh:
        for line in cf_contents:
            fh.write(line)
