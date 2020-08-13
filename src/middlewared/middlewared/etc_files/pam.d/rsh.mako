#
# $FreeBSD: head/etc/pam.d/rsh 170510 2007-06-10 18:57:20Z yar $
#
# PAM configuration for the "rsh" service
#

# auth
auth		required	pam_rhosts.so		no_warn

# account
account		required	pam_nologin.so
account		required	pam_unix.so

# session
session		required	pam_permit.so

# password
password	required	pam_deny.so
