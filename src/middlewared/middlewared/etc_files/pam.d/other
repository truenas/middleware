#
# $FreeBSD: head/etc/pam.d/other 197769 2009-10-05 09:28:54Z des $
#
# PAM configuration for the "other" service
#

# auth
auth		sufficient	pam_opie.so		no_warn no_fake_prompts
auth		requisite	pam_opieaccess.so	no_warn allow_local
#auth		sufficient	pam_krb5.so		no_warn try_first_pass
#auth		sufficient	pam_ssh.so		no_warn try_first_pass
auth		required	pam_unix.so		no_warn try_first_pass

# account
account		required	pam_nologin.so
#account	required	pam_krb5.so
account		required	pam_login_access.so
account		required	pam_unix.so

# session
#session	optional	pam_ssh.so		want_agent
session		required	pam_permit.so

# password
password	required	pam_permit.so
