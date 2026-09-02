# PAM configuration for the TrueNAS S3 service. The service verifies the
# SigV4 signature itself and consults PAM for the account check only, so
# a local or directory services account that may log in may use S3.

auth		required	pam_deny.so
@include common-account
password	required	pam_deny.so
session		required	pam_permit.so
