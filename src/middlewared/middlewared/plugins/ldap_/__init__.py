import sys
# nss-pam-ldapd generates constants at compile time that are stored in python
# nslcd client files in /usr/share/nslcd-utils. Hence, path is expanded to include
# this for the middleware nslcd client
sys.path.append('/usr/share/nslcd-utils')
