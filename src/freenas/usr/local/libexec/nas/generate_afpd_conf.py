#!/usr/local/bin/python
import os
import textwrap

import netif

from middlewared.client import Client
from middlewared.client.utils import Struct


def get_interface(ipaddress):
    get_all_ifaces = netif.list_interfaces()
    ifaces = []
    for iface in get_all_ifaces.keys():
        all_ip = [a.__getstate__()['address'] for a in netif.get_interface(iface).addresses if a.af == netif.AddressFamily.INET]
        is_ip_exist = list(set(ipaddress).intersection(all_ip))
        if is_ip_exist:
            ifaces.append(iface)

    return ifaces


def main():
    """Use the django ORM to generate a config file.  We'll build the
    config file as a series of lines, and once that is done write it
    out in one go"""

    map_acls_mode = False
    afp_config = "/usr/local/etc/afp.conf"
    cf_contents = []
    client = Client()

    afp = Struct(client.call('datastore.query', 'services.afp', None, {'get': True}))

    cf_contents.append("[Global]\n")
    uam_list = ['uams_dhx.so', 'uams_dhx2.so']
    if afp.afp_srv_guest:
        uam_list.append('uams_guest.so')
        cf_contents.append('\tguest account = %s\n' % afp.afp_srv_guest_user)
    # uams_gss.so bails out with an error if kerberos isn't configured
    if client.call('datastore.query', 'directoryservice.kerberoskeytab', None, {'count': True}) > 0:
        uam_list.append('uams_gss.so')
    cf_contents.append('\tuam list = %s\n' % (" ").join(uam_list))

    if afp.afp_srv_bindip:
        ifaces = get_interface(afp.afp_srv_bindip)
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

    if afp.afp_srv_map_acls == 'mode' and client.call('notifier.common', 'system', 'activedirectory_enabled'):
        map_acls_mode = True

    if map_acls_mode:
        ad = Struct(client.call('notifier.directoryservice', 'AD'))

        cf_contents.append("\tldap auth method = %s\n" % "simple")
        cf_contents.append("\tldap auth dn = %s\n" % ad.binddn)
        cf_contents.append("\tldap auth pw = %s\n" % ad.bindpw)
        cf_contents.append("\tldap server = %s\n" % ad.domainname)

        # This should be configured when using this option
        if ad.userdn:
            cf_contents.append("\tldap userbase = %s\n" % ad.userdn)

        cf_contents.append("\tldap userscope = %s\n" % "sub")

        # This should be configured when using this option
        if ad.groupdn:
            cf_contents.append("\tldap groupbase = %s\n" % ad.groupdn)

        cf_contents.append("\tldap groupscope = %s\n" % "sub")

        cf_contents.append("\tldap user filter = %s\n" % "objectclass=user")
        cf_contents.append("\tldap group filter = %s\n" % "objectclass=group")
        cf_contents.append("\tldap uuid attr = %s\n" % "objectGUID")
        cf_contents.append("\tldap uuid encoding = %s\n" % "ms-guid")
        cf_contents.append("\tldap name attr = %s\n" % "sAMAccountName")
        cf_contents.append("\tldap group attr = %s\n" % "sAMAccountName")

    cf_contents.append("\tlog file = %s\n" % "/var/log/afp.log")
    cf_contents.append("\tlog level = %s\n" % "default:info")
    cf_contents.append("\n")

    for share in client.call('datastore.query', 'sharing.afp_share'):
        share = Struct(share)
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
        timemachine_quota_plist_managed_flag = os.path.join(share.afp_path, ".com.apple.TimeMachine.quota.plist.FreeNAS-managed")
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


if __name__ == "__main__":
    main()
