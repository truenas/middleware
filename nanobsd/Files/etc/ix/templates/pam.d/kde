#
# $FreeBSD: src/etc/pam.d/kde,v 1.9 2009/10/05 09:28:54 des Exp $
#
# PAM configuration for the "kde" service
#

# auth
#auth		sufficient	pam_krb5.so		no_warn try_first_pass
#auth		sufficient	pam_ssh.so		no_warn try_first_pass
auth		required	pam_unix.so		no_warn try_first_pass

# account
account		required	pam_nologin.so
#account	required	pam_krb5.so
account		required	pam_unix.so

# session
#session	optional	pam_ssh.so		want_agent
session		required	pam_permit.so
