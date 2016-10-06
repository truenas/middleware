#!/usr/local/bin/python
from middlewared.client import Client
from middlewared.client.utils import Struct


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
        cf_contents.append("\tafp listen = %s\n" % ' '.join(afp.afp_srv_bindip))
    cf_contents.append("\tmax connections = %s\n" % afp.afp_srv_connections_limit)
    cf_contents.append("\tmimic model = RackMac\n")
    if afp.afp_srv_dbpath:
        cf_contents.append("\tvol dbnest = no\n")
        cf_contents.append("\tvol dbpath = %s\n" % afp.afp_srv_dbpath)
    else:
        cf_contents.append("\tvol dbnest = yes\n")
    if afp.afp_srv_global_aux:
        cf_contents.append("\t%s" % afp.afp_srv_global_aux.encode('utf8'))

    if afp.afp_srv_map_acls:
        cf_contents.append("\tmap acls = %s\n" % afp.afp_srv_map_acls)

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

    cf_contents.append("\n")

    if afp.afp_srv_homedir_enable:
        cf_contents.append("[Homes]\n")
        cf_contents.append("\tbasedir regex = %s\n" % afp.afp_srv_homedir)
        if afp.afp_srv_homename:
            cf_contents.append("\thome name = %s\n" % afp.afp_srv_homename)
        cf_contents.append("\n")

    for share in client.call('datastore.query', 'sharing.afp_share'):
        share = Struct(share)
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

    with open(afp_config, "w") as fh:
        for line in cf_contents:
            fh.write(line)

if __name__ == "__main__":
    main()
