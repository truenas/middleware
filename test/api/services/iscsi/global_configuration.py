#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../../conn/')
import conn

service = 'globalconfiguration'
headers = conn.headers
auth = conn.auth
payload = {
          "iscsi_multithreaded": False,
          "iscsi_maxconnect": 20,
          "iscsi_luc_authnetwork": "",
          "iscsi_iotimeout": 30,
          "iscsi_lucip": "127.0.0.1",
          "iscsi_firstburst": 65536,
          "iscsi_r2t": 32,
          "iscsi_discoveryauthmethod": "None",
          "iscsi_defaultt2w": 2,
          "iscsi_maxrecdata": 262144,
          "iscsi_basename": "iqn.2011-03.org.example.istgt",
          "iscsi_defaultt2r": 60,
          "iscsi_nopinint": 20,
          "iscsi_maxburst": 262144,
          "iscsi_toggleluc": False,
          "iscsi_lucport": 3261,
          "iscsi_maxsesh": 16,
          "iscsi_luc_authgroup": None, 
          "iscsi_luc_authmethod": "",
          "iscsi_maxoutstandingr2t": 16,
}

url = conn.url + 'services/iscsi/' + service + '/1/'
r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
print r.status_code
result = json.loads(r.text)
for items in result:
  print items+':',result[items]
r = requests.get(url, auth = auth)
result = json.loads(r.text)
#for items in result:
#  print items+':',result[items]
