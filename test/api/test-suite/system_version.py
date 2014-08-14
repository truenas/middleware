#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
auth = conn.auth
url = conn.url + 'system/version/'
headers = conn.headers

def get():
  print 'Getting system-version ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items+':', result[items]
    print 'Get system-version succeeded!'

def put():
  print 'No PUT function for system-version!'

def post():
  print 'No POST function for system-version!'

def delete():
  print 'No DELETE function for system-version!'

