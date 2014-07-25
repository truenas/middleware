#!/usr/local/bin/python

import requests
import json
import sys
import conn

headers = conn.headers
auth = conn.auth
url = conn.url + 'system/ntpserver/'
payload = {
          "ntp_minpoll": 6,
          "ntp_maxpoll": 10,
          "ntp_prefer": "false",
          "ntp_address": "br.pool.ntp.org",
          "ntp_burst": "false",
          "ntp_iburst": "true"
}

def get():
  print 'Getting system-NTPServer ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print '\n'
      for items in result[i]:
        print items+':', result[i][items]
    print 'Get system-NTPServer --> Succeeded!'
  else:
    print 'Get system-NTPServer --> Failed!'

def post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create system-NTPServer --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create system-NTPServer --> Failed!'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update system-NTPServer --> Succeeded!' 
  else:
    print 'Update system-NTPServer --> Failed!'

def delete():
  id = post()
  r = requests.delete(url+id, auth = auth) 
  if r.status_code == 204:
    print 'Delete system-NTPServer --> Succeeded!'
  else:
    print 'Delete system-NTPServer --> Failed!'


