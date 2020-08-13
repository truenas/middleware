#
# $FreeBSD: head/etc/pam.d/passwd 113967 2003-04-24 12:22:42Z des $
#
# PAM configuration for the "passwd" service
#

# passwd(1) does not use the auth, account or session services.

# password
#password	requisite	pam_passwdqc.so		enforce=users
password	required	pam_unix.so		no_warn try_first_pass nullok
