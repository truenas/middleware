# Pam configuration for API key authentication

auth		[success=1 default=die]		pam_tdb.so
@include common-auth-unix
@include common-account
password	required			pam_deny.so
session		required			pam_deny.so
