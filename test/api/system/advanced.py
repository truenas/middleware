#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

headers = conn.headers
auth = conn.auth
url = conn.url + 'system/advanced/'
payload = {
          "adv_serialconsole": 'false',
          "adv_traceback": 'true',
          "adv_uploadcrash": 'true',
          "adv_consolescreensaver": 'false',
          "adv_debugkernel": 'false',
          "adv_advancedmode": 'false',
          "adv_consolemsg": 'false',
          "adv_anonstats": 'true',
          "adv_autotune": 'false',
          "adv_powerdaemon": 'false',
          "adv_swapondrive": 2,
          "adv_anonstats_token": "",
          "adv_motd": "Welcome to FreeNAS",
          "adv_consolemenu": 'true',
          "id": 1,
          "adv_serialport": "0x2f8",
          "adv_serialspeed": "9600"
}

#r = requests.get(url, auth = auth)
r = requests.put(url, auth = auth, headers = headers, data = json.dumps(payload))
result = json.loads(r.text)
for items in result:
  print items+':', result[items]
