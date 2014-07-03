#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

auth = conn.auth
headers = conn.headers
url = conn.url + 'jails/jails/'
payload = {
    "jail_alias_bridge_ipv4": "null",
    "jail_alias_bridge_ipv6": "null",
    "jail_alias_ipv4": "null",
    "jail_alias_ipv6": "null",
    "jail_autostart": "true",
    "jail_bridge_ipv4": "null",
    "jail_bridge_ipv4_netmask": "",
    "jail_bridge_ipv6": "null",
    "jail_bridge_ipv6_prefix": "",
    "jail_defaultrouter_ipv4": "null",
    "jail_defaultrouter_ipv6": "null",
    "jail_flags": "allow.raw_sockets=true",
    "jail_host": "transmission_1",
    "jail_ipv4": "192.168.3.2",
    "jail_ipv4_netmask": "24",
    "jail_ipv6": "null",
    "jail_ipv6_prefix": "",
    "jail_mac": "02:c3:79:00:08:0b",
    "jail_nat": "false",
    "jail_status": "Running",
    "jail_type": "pluginjail",
    "jail_vnet": "true"
}
payload2 = {
    "jail_host": "test",
    "jail_type": "pluginjail"
}

def jails_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def jails_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  print r.text
  print r.status_code

while(1):
  method = raw_input('Input method:')
  if method == 'get':
    jails_get()
  elif method == 'post':
    jails_post()
