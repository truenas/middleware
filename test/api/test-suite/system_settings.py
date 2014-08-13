#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
headers = conn.headers
auth = conn.auth
url = conn.url + 'system/settings/'
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


def put():
  r = requests.put(url, auth = auth, headers = headers, data = json.dumps(payload))
  result = json.loads(r.text)
  if r.status_code == 200:
    print 'Update system-settings --> Succeeded!'
  else:
    print 'Update system-settings --> Failed!'

def get():
  print 'Getting system-settings ......'
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if r.status_code == 200:                                                   
    for items in result:
      print items+':', result[items]
    print 'Get system-settings --> Succeeded!'
  else:
    print 'Get system-settings --> Failed!'

def post():
  print 'No POST function for system-settings!'

def delete():
  print 'No DELETE function for systems-settings!'
