#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

headers = conn.headers
auth = conn.auth
payload = {
          "ftp_anonuserbw": 0,
          "ftp_ident": False,
          "ftp_timeout": 600,
          "ftp_resume": False,
          "ftp_options": "",
          "ftp_masqaddress": "",
          "ftp_rootlogin": False,
          "id": 1,
          "ftp_passiveportsmax": 0,
          "ftp_ipconnections": 2,
          "ftp_defaultroot": True,
          "ftp_dirmask": "022",
          "ftp_passiveportsmin": 0,
          "ftp_onlylocal": False,
          "ftp_loginattempt": 1,
          "ftp_localuserbw": 0,
          "ftp_port": 21,
          "ftp_onlyanonymous": False,
          "ftp_reversedns": False,
          "ftp_anonuserdlbw": 0,
          "ftp_clients": 20,
          "ftp_tls": False,
          "ftp_tls_opt_allow_client_renegotiations": False,
          "ftp_tls_opt_allow_dot_login": False,
          "ftp_tls_opt_allow_per_user": False,
          "ftp_tls_opt_common_name_required": False,
          "ftp_tls_opt_dns_name_required": False,
          "ftp_tls_opt_enable_diags": False,
          "ftp_tls_opt_export_cert_data": False,
          "ftp_tls_opt_ip_address_required": False,
          "ftp_tls_opt_no_cert_request": False,
          "ftp_tls_opt_no_empty_fragments": False,
          "ftp_tls_opt_no_session_reuse_required": False,
          "ftp_tls_opt_stdenvvars": False,
          "ftp_tls_opt_use_implicit_ssl": False,
          "ftp_tls_policy": "on",
          "ftp_fxp": False,
          "ftp_filemask": "077",
          "ftp_localuserdlbw": 0,
          "ftp_banner": "",
          "ftp_ssltls_certfile": "",
          "ftp_anonpath": "/mnt/tank0/"
}

url = conn.url + 'services/ftp/' 

r = requests.put(url,auth=auth,headers=headers,data=json.dumps(payload))
#r = requests.get(url,auth=auth)
print r.status_code
result = json.loads(r.text)
for items in result:
  print items,':',result[items]


