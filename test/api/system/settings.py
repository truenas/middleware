#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

service = 'settings'
headers = conn.headers
auth = conn.auth
payload = {
          "stg_timezone": "America/Los_Angeles",
          "stg_guiport": 80,
          "stg_guihttpsport": 443,
          "stg_guiprotocol": "http",
          "stg_guiv6address": "::",
          "stg_syslogserver": "",
          "stg_language": "en",
          "stg_directoryservice": "",
          "stg_guiaddress": "0.0.0.0",
          "stg_kbdmap": "",
          "id": 1
}
url = conn.url + 'system/' + service + '/' 

r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)

result = json.loads(r.text)
for items in result:
  print items,':',result[items]


