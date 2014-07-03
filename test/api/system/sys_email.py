#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

auth = conn.auth
url = conn.url + 'system/email/'
headers = conn.headers
payload =  {
          "em_fromemail": "william.spam@ixsystems.com",
          "em_outgoingserver": "mail.ixsystems.com",
          "em_pass": "changeme",
          "em_port": 25,
          "em_security": "plain",
          "em_smtp": "true",
          "em_user": "william.spam@ixsystems.com"
}

r = requests.get(url, auth = auth)
r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
result = json.loads(r.text)
for items in result:
  print items+':', result[items]
