#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

auth = conn.auth
headers = conn.headers
url = conn.url + 'jails/configuration/'
payload = {
    "jc_collectionurl": "http://download.freenas.org/latest/RELEASE/x64/jails",
    "jc_ipv4_network": "10.2.0.0/16",
    "jc_ipv4_network_end": "10.2.255.254",
    "jc_ipv4_network_start": "10.2.0.1",
    "jc_ipv6_network": "",
    "jc_ipv6_network_end": "",
    "jc_ipv6_network_start": "",
    "jc_path": "/mnt/tank/jails"
}

def jails_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for items in result:
    print items+':', result[items]

def jails_put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items + ':', result[items]

while(1):
  method = raw_input('Input method:')
  if method == 'get':
    jails_get()
  elif method == 'put':
    jails_put()
