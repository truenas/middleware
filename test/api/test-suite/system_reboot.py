#!/usr/local/bin/python

import requests
import json
import sys
import conn

headers = conn.headers
url = conn.url + 'system/reboot/'
auth = conn.auth

def post():
  r = requests.post(url, auth = auth, headers = headers)
  if r.status_code == 202:
    print 'System rebooting ......'
  else:
    print 'System reboot --> Failed'

def put():
  print 'No PUT function for system-reboot!'

def get():
  print 'No GET function for system-reboot!'

def delete():
  print 'No DELETE function for system-reboot!'

