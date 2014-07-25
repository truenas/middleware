#!/usr/local/bin/python

import requests
import json
import sys
import conn

headers = conn.headers
url = conn.url + 'system/shutdown/'
auth = conn.auth

def post():
  r = requests.post(url, auth = auth, headers = headers)
  if r.status_code == 202:
    print 'System shuting down ......'
  else:
    print 'System shut down --> Failed'

def put():
  print 'No PUT function for system-shutdown!'

def get():
  print 'No GET function for system-shutdown!'

def delete():
  print 'No DELETE function for system-shutdown!'
