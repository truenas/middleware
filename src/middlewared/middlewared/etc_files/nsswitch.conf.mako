#
# nsswitch.conf(5) - name service switch configuration file
# $FreeBSD$
#
<%
        def safe_call(*args):
            try:
                val = middleware.call_sync(*args)
            except:
                val = False
            return val

        ad_enabled = safe_call('activedirectory.config')['enable']
        ldap_enabled = safe_call('ldap.config')['enable']
        nis_enabled = IS_FREEBSD and safe_call('nis.config')['enable']

        group = ['files']
        hosts = ['files', 'dns']
        passwd = ['files']
        sudoers = ['files']

        if ldap_enabled:
            group.append('ldap')
            passwd.append('ldap')

        if nis_enabled:
            group.append('nis')
            hosts.append('nis')
            passwd.append('nis')

        if ad_enabled:
            group.append('winbind')
            passwd.append('winbind')
%>

group: ${' '.join(group)}
hosts: ${' '.join(hosts)}
networks: files
passwd: ${' '.join(passwd)}
shells: files
services: files
protocols: files
rpc: files
sudoers: files 
