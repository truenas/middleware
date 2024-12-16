#
# /etc/pam.d/common-password - password-related modules common to all services
#
# This file is included from other service-specific PAM config files,
# and should contain a list of modules that define the services to be
# used to change user passwords.  The default is pam_unix.
#
# The ability to change password via PAM is disabled on TrueNAS. Any account
# password changes should be made through the TrueNAS middleware

password	requisite			pam_deny.so
password	required			pam_permit.so
