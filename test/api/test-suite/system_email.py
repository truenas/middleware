#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
auth = conn.auth
url = conn.url + 'system/email/'
headers = conn.headers
payload =  {
          "em_fromemail": "root@freenas.local",
          "em_outgoingserver": "",
          "em_pass": None,
          "em_port": 25,
          "em_security": "plain",
          "em_smtp": "false",
          "em_user": None
}

def put():
  r = requests.put(url, auth = auth, headers = headers, data = json.dumps(payload))
  result = json.loads(r.text)
  if r.status_code == 200:
    print 'Update system-email Succeeded!'
  else:
    print 'Update system-email Failed!'

def get():
  print 'Getting system-email ......'
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if r.status_code == 200:
    for items in result:
      print items+':', result[items]
    print 'Get system-email Succeeded!'
  else:
    print 'Get system-email Failed!'

def post():
  print 'No POST function for system-email!'

def delete():
  print 'No DELETE function for system-email!'

